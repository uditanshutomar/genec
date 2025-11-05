package com.genec.jdt;

import org.eclipse.jdt.core.*;
import org.eclipse.jdt.core.dom.*;
import org.eclipse.jdt.core.dom.rewrite.ASTRewrite;
import org.eclipse.jdt.core.dom.rewrite.ListRewrite;
import org.eclipse.jface.text.Document;
import org.eclipse.text.edits.TextEdit;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

/**
 * Eclipse JDT-based Extract Class refactoring implementation.
 *
 * This class handles the actual AST parsing and code generation using
 * Eclipse JDT APIs instead of string manipulation.
 */
public class EclipseJDTRefactoring {

    private RefactoringSpec spec;
    private CompilationUnit compilationUnit;
    private AST ast;
    private String originalSource;
    private TypeDeclaration originalTypeDecl;
    private Map<String, FieldMetadata> extractedFieldMetadata;

    private static class FieldMetadata {
        final String name;
        final Type type;
        final boolean isFinal;
        final boolean isStatic;
        final List<Modifier.ModifierKeyword> otherModifiers;
        final Expression initializer;

        FieldMetadata(String name, Type type, boolean isFinal, boolean isStatic,
                      List<Modifier.ModifierKeyword> otherModifiers,
                      Expression initializer) {
            this.name = name;
            this.type = type;
            this.isFinal = isFinal;
            this.isStatic = isStatic;
            this.otherModifiers = otherModifiers;
            this.initializer = initializer;
        }
    }

    private static class ExtractedFieldInfo {
        final String name;
        final FieldDeclaration declaration;
        final boolean isFinal;
        final Type originalType;

        ExtractedFieldInfo(String name, FieldDeclaration declaration, boolean isFinal, Type originalType) {
            this.name = name;
            this.declaration = declaration;
            this.isFinal = isFinal;
            this.originalType = originalType;
        }
    }

    public EclipseJDTRefactoring(RefactoringSpec spec) {
        this.spec = spec;
    }

    /**
     * Execute the Extract Class refactoring.
     *
     * @return RefactoringResult with generated code
     */
    public RefactoringResult execute() {
        try {
            // 1. Read and parse the original Java file
            originalSource = readFile(spec.getClassFile());
            parseJavaFile();

            // 2. Find the class declaration
            findClassDeclaration();

            if (originalTypeDecl == null) {
                return new RefactoringResult(
                    false,
                    "Could not find class declaration in file: " + spec.getClassFile()
                );
            }

            // 3. Generate the new extracted class
            String newClassCode = generateExtractedClass();

            // 4. Generate the modified original class
            String modifiedOriginalCode = generateModifiedOriginal();

            // 5. Compute new class file path
            String newClassPath = computeNewClassPath();

            return new RefactoringResult(
                true,
                "Successfully extracted " + spec.getMethods().size() + " methods into " + spec.getNewClassName(),
                newClassCode,
                modifiedOriginalCode,
                newClassPath
            );

        } catch (Exception e) {
            return new RefactoringResult(
                false,
                "Refactoring failed: " + e.getMessage() + "\n" + getStackTrace(e)
            );
        }
    }

    /**
     * Parse the Java source file using Eclipse JDT.
     */
    private void parseJavaFile() {
        ASTParser parser = ASTParser.newParser(AST.JLS17);
        parser.setSource(originalSource.toCharArray());
        parser.setKind(ASTParser.K_COMPILATION_UNIT);
        parser.setResolveBindings(false);

        CompilationUnit parsedCU = (CompilationUnit) parser.createAST(null);

        // Record modifications on the parsed compilation unit so ASTRewrite can track edits
        parsedCU.recordModifications();

        compilationUnit = parsedCU;
        ast = compilationUnit.getAST();
    }

    /**
     * Find the main class declaration in the compilation unit.
     */
    private void findClassDeclaration() {
        List<AbstractTypeDeclaration> types = compilationUnit.types();
        for (AbstractTypeDeclaration type : types) {
            if (type instanceof TypeDeclaration) {
                originalTypeDecl = (TypeDeclaration) type;
                break;
            }
        }
    }

    /**
     * Generate the new extracted class code.
     */
    private String generateExtractedClass() throws Exception {
        // Create a new AST for the extracted class (with recording enabled)
        AST newAst = AST.newAST(AST.JLS17, true);
        CompilationUnit newCu = newAst.newCompilationUnit();

        // Copy package declaration
        if (compilationUnit.getPackage() != null) {
            PackageDeclaration pkgDecl = newAst.newPackageDeclaration();
            pkgDecl.setName(newAst.newName(compilationUnit.getPackage().getName().getFullyQualifiedName()));
            newCu.setPackage(pkgDecl);
        }

        // Copy import declarations
        for (Object importObj : compilationUnit.imports()) {
            ImportDeclaration importDecl = (ImportDeclaration) importObj;
            ImportDeclaration newImport = newAst.newImportDeclaration();
            newImport.setName(newAst.newName(importDecl.getName().getFullyQualifiedName()));
            newImport.setOnDemand(importDecl.isOnDemand());
            newImport.setStatic(importDecl.isStatic());
            newCu.imports().add(newImport);
        }

        // Create the new class
        TypeDeclaration newClass = newAst.newTypeDeclaration();
        newClass.setName(newAst.newSimpleName(spec.getNewClassName()));
        newClass.modifiers().add(newAst.newModifier(Modifier.ModifierKeyword.PUBLIC_KEYWORD));

        // Add Javadoc
        Javadoc javadoc = newAst.newJavadoc();
        TagElement tag = newAst.newTagElement();
        TextElement text = newAst.newTextElement();
        text.setText("Extracted class generated by GenEC using Eclipse JDT.");
        tag.fragments().add(text);
        javadoc.tags().add(tag);
        newClass.setJavadoc(javadoc);

        // Extract fields that should be moved
        Set<String> fieldNames = new HashSet<>(spec.getFields() != null ? spec.getFields() : Collections.emptyList());

        // Also extract static fields referenced by extracted methods
        Set<String> methodSignatures = normalizeMethodSignatures(spec.getMethods());
        Set<String> referencedStaticFields = findReferencedStaticFields(methodSignatures);
        fieldNames.addAll(referencedStaticFields);

        Map<String, ExtractedFieldInfo> extractedFields = extractFields(newAst, fieldNames);
        for (ExtractedFieldInfo fieldInfo : extractedFields.values()) {
            newClass.bodyDeclarations().add(fieldInfo.declaration);
        }

        // Add reference to original class (for delegation pattern)
        if (!extractedFields.isEmpty()) {
            // Add a field to store reference to original class for accessing non-extracted members
            String originalClassName = originalTypeDecl.getName().getIdentifier();
            VariableDeclarationFragment fragment = newAst.newVariableDeclarationFragment();
            fragment.setName(newAst.newSimpleName(toCamelCase(originalClassName)));

            FieldDeclaration referenceField = newAst.newFieldDeclaration(fragment);
            referenceField.setType(newAst.newSimpleType(newAst.newSimpleName(originalClassName)));
            referenceField.modifiers().add(newAst.newModifier(Modifier.ModifierKeyword.PRIVATE_KEYWORD));

            // Only add if methods need access to original class
            // For now, we'll add it to be safe
            // newClass.bodyDeclarations().add(0, referenceField);
        }

        // Extract methods that should be moved
        List<MethodDeclaration> extractedMethods = extractMethods(newAst, methodSignatures, extractedFields.keySet());
        for (MethodDeclaration method : extractedMethods) {
            newClass.bodyDeclarations().add(method);
        }

        // Add accessors for extracted fields to maintain encapsulation
        addFieldAccessors(newAst, newClass, extractedFields);

        // Qualify calls to original static helpers that remain in the source class
        // IMPORTANT: Only qualify calls to methods that were NOT extracted
        final Set<String> extractedMethodNames = new HashSet<>();
        for (MethodDeclaration method : extractedMethods) {
            extractedMethodNames.add(method.getName().getIdentifier());
        }
        final Set<String> originalMethodNames = new HashSet<>();
        for (Object decl : originalTypeDecl.bodyDeclarations()) {
            if (decl instanceof MethodDeclaration) {
                MethodDeclaration originalMethod = (MethodDeclaration) decl;
                originalMethodNames.add(originalMethod.getName().getIdentifier());
            }
        }
        final String originalClassName = originalTypeDecl.getName().getIdentifier();

        // Visit each extracted method to qualify calls to non-extracted methods
        for (MethodDeclaration extractedMethod : extractedMethods) {
            extractedMethod.accept(new ASTVisitor() {
                @Override
                public boolean visit(MethodInvocation node) {
                    // Only process unqualified method calls
                    if (node.getExpression() == null) {
                        String invokedName = node.getName().getIdentifier();
                        // If this call is to a method that exists in original class but was NOT extracted,
                        // qualify it with the original class name
                        if (originalMethodNames.contains(invokedName) && !extractedMethodNames.contains(invokedName)) {
                            node.setExpression(newAst.newSimpleName(originalClassName));
                        }
                    }
                    return true;
                }
            });
        }

        newCu.types().add(newClass);

        // Convert newly created AST to source code
        // For a newly constructed AST (not a modification), we just use toString()
        return newCu.toString();
    }

    /**
     * Generate the modified original class (with extracted methods removed).
     */
    private String generateModifiedOriginal() throws Exception {
        // Create a rewrite to modify the original AST
        ASTRewrite rewrite = ASTRewrite.create(ast);

        // Get the list rewrite for the type's body declarations
        ListRewrite listRewrite = rewrite.getListRewrite(originalTypeDecl, TypeDeclaration.BODY_DECLARATIONS_PROPERTY);

        // Find methods to extract and replace their bodies with delegation to helper class
        Set<String> methodSignatures = normalizeMethodSignatures(spec.getMethods());
        String helperFieldName = toCamelCase(spec.getNewClassName());
        boolean needsHelperField = false;
        for (Object bodyDecl : originalTypeDecl.bodyDeclarations()) {
            if (bodyDecl instanceof MethodDeclaration) {
                MethodDeclaration method = (MethodDeclaration) bodyDecl;
                String signature = getMethodSignature(method);
                if (methodSignatures.contains(signature)) {
                    boolean isStaticMethod = Modifier.isStatic(method.getModifiers());
                    if (!isStaticMethod) {
                        needsHelperField = true;
                    }

                    Block newBody = ast.newBlock();

                    MethodInvocation invocation = ast.newMethodInvocation();
                    if (isStaticMethod) {
                        invocation.setExpression(ast.newSimpleName(spec.getNewClassName()));
                    } else {
                        invocation.setExpression(ast.newSimpleName(helperFieldName));
                    }
                    invocation.setName(ast.newSimpleName(method.getName().getIdentifier()));

                    List<SingleVariableDeclaration> params = method.parameters();
                    for (SingleVariableDeclaration param : params) {
                        invocation.arguments().add(ast.newSimpleName(param.getName().getIdentifier()));
                    }

                    boolean isVoid = method.getReturnType2() == null;
                    if (!isVoid) {
                        Type returnType = method.getReturnType2();
                        if (returnType.isPrimitiveType()) {
                            PrimitiveType primitive = (PrimitiveType) returnType;
                            isVoid = primitive.getPrimitiveTypeCode() == PrimitiveType.VOID;
                        }
                    }

                    Statement delegateStatement;
                    if (isVoid) {
                        delegateStatement = ast.newExpressionStatement(invocation);
                    } else {
                        ReturnStatement returnStatement = ast.newReturnStatement();
                        returnStatement.setExpression(invocation);
                        delegateStatement = returnStatement;
                    }

                    newBody.statements().add(delegateStatement);
                    rewrite.set(method, MethodDeclaration.BODY_PROPERTY, newBody, null);
                }
            }
        }

        // Find and remove extracted fields
        Set<String> fieldNames = new HashSet<>(spec.getFields() != null ? spec.getFields() : Collections.emptyList());
        for (Object bodyDecl : originalTypeDecl.bodyDeclarations()) {
            if (bodyDecl instanceof FieldDeclaration) {
                FieldDeclaration field = (FieldDeclaration) bodyDecl;
                List<VariableDeclarationFragment> fragments = field.fragments();
                List<VariableDeclarationFragment> toRemove = new ArrayList<>();

                for (VariableDeclarationFragment fragment : fragments) {
                    if (fieldNames.contains(fragment.getName().getIdentifier())) {
                        toRemove.add(fragment);
                    }
                }

                // If all fragments are extracted, remove the entire field declaration
                if (toRemove.size() == fragments.size()) {
                    listRewrite.remove(field, null);
                } else {
                    // Otherwise, remove individual fragments
                    for (VariableDeclarationFragment fragment : toRemove) {
                        ListRewrite fragmentRewrite = rewrite.getListRewrite(field, FieldDeclaration.FRAGMENTS_PROPERTY);
                        fragmentRewrite.remove(fragment, null);
                    }
                }
            }
        }

        Map<String, FieldMetadata> fieldMetadata = collectExtractedFieldMetadata();
        Map<String, String> getterNames = new HashMap<>();
        Map<String, String> setterNames = new HashMap<>();
        Map<String, String> preIncrementNames = new HashMap<>();
        Map<String, String> postIncrementNames = new HashMap<>();
        Map<String, String> preDecrementNames = new HashMap<>();
        Map<String, String> postDecrementNames = new HashMap<>();
        for (String fieldName : fieldNames) {
            FieldMetadata metadata = fieldMetadata.get(fieldName);
            if (metadata == null) {
                continue;
            }
            getterNames.put(fieldName, "get" + capitalize(fieldName));
            setterNames.put(fieldName, "set" + capitalize(fieldName));
            if (supportsIncrementOperations(metadata.type) && !metadata.isFinal) {
                preIncrementNames.put(fieldName, "increment" + capitalize(fieldName));
                postIncrementNames.put(fieldName, "postIncrement" + capitalize(fieldName));
                preDecrementNames.put(fieldName, "decrement" + capitalize(fieldName));
                postDecrementNames.put(fieldName, "postDecrement" + capitalize(fieldName));
            }
        }

        final Set<String> extractedFieldNames = new HashSet<>(fieldNames);

        if (needsHelperField && !extractedFieldNames.isEmpty()) {
            originalTypeDecl.accept(new ASTVisitor() {
                @Override
                public boolean visit(SimpleName node) {
                    String identifier = node.getIdentifier();
                    if (!extractedFieldNames.contains(identifier)) {
                        return true;
                    }
                    replaceFieldReference(
                        rewrite,
                        node,
                        identifier,
                        helperFieldName,
                        getterNames,
                        setterNames,
                        preIncrementNames,
                        postIncrementNames,
                        preDecrementNames,
                        postDecrementNames
                    );
                    return false;
                }

                @Override
                public boolean visit(FieldAccess node) {
                    if (!(node.getExpression() instanceof ThisExpression)) {
                        return true;
                    }
                    String identifier = node.getName().getIdentifier();
                    if (!extractedFieldNames.contains(identifier)) {
                        return true;
                    }
                    replaceFieldReference(
                        rewrite,
                        node,
                        identifier,
                        helperFieldName,
                        getterNames,
                        setterNames,
                        preIncrementNames,
                        postIncrementNames,
                        preDecrementNames,
                        postDecrementNames
                    );
                    return false;
                }
            });
        }

        if (needsHelperField) {
            // Add field for the extracted class instance
            VariableDeclarationFragment fragment = ast.newVariableDeclarationFragment();
            fragment.setName(ast.newSimpleName(helperFieldName));

            ClassInstanceCreation helperInit = ast.newClassInstanceCreation();
            helperInit.setType(ast.newSimpleType(ast.newSimpleName(spec.getNewClassName())));
            fragment.setInitializer(helperInit);

            FieldDeclaration newField = ast.newFieldDeclaration(fragment);
            newField.setType(ast.newSimpleType(ast.newSimpleName(spec.getNewClassName())));
            newField.modifiers().add(ast.newModifier(Modifier.ModifierKeyword.PRIVATE_KEYWORD));

            // Add Javadoc
            Javadoc javadoc = ast.newJavadoc();
            TagElement tag = ast.newTagElement();
            TextElement text = ast.newTextElement();
            text.setText("Extracted functionality - created by GenEC refactoring.");
            tag.fragments().add(text);
            javadoc.tags().add(tag);
            newField.setJavadoc(javadoc);

            listRewrite.insertFirst(newField, null);
        }

        // Apply changes to document
        Document document = new Document(originalSource);
        TextEdit edits = rewrite.rewriteAST(document, null);
        edits.apply(document);

        return document.get();
    }

    /**
     * Find static fields that are referenced by the methods being extracted.
     * Static fields should be moved with the methods that use them.
     */
    private Set<String> findReferencedStaticFields(Set<String> methodSignatures) {
        Set<String> referencedFields = new HashSet<>();

        // Get all static fields in the class
        Map<String, Boolean> staticFields = new HashMap<>();
        for (Object bodyDecl : originalTypeDecl.bodyDeclarations()) {
            if (bodyDecl instanceof FieldDeclaration) {
                FieldDeclaration field = (FieldDeclaration) bodyDecl;
                if (Modifier.isStatic(field.getModifiers())) {
                    for (Object fragmentObj : field.fragments()) {
                        VariableDeclarationFragment fragment = (VariableDeclarationFragment) fragmentObj;
                        staticFields.put(fragment.getName().getIdentifier(), true);
                    }
                }
            }
        }

        // Find which static fields are referenced in extracted methods
        for (Object bodyDecl : originalTypeDecl.bodyDeclarations()) {
            if (bodyDecl instanceof MethodDeclaration) {
                MethodDeclaration method = (MethodDeclaration) bodyDecl;
                String signature = getMethodSignature(method);

                if (methodSignatures.contains(signature)) {
                    // Visit this method's AST to find field references
                    method.accept(new ASTVisitor() {
                        @Override
                        public boolean visit(SimpleName node) {
                            String name = node.getIdentifier();
                            if (staticFields.containsKey(name)) {
                                // Check if this is actually a field reference (not a method call or variable)
                                ASTNode parent = node.getParent();
                                if (!(parent instanceof MethodInvocation &&
                                      ((MethodInvocation) parent).getName() == node)) {
                                    referencedFields.add(name);
                                }
                            }
                            return true;
                        }

                        @Override
                        public boolean visit(FieldAccess node) {
                            String name = node.getName().getIdentifier();
                            if (staticFields.containsKey(name)) {
                                referencedFields.add(name);
                            }
                            return true;
                        }
                    });
                }
            }
        }

        return referencedFields;
    }

    /**
     * Extract fields from original class that should be moved to new class.
     */
    private Map<String, FieldMetadata> collectExtractedFieldMetadata() {
        if (extractedFieldMetadata != null) {
            return extractedFieldMetadata;
        }

        Map<String, FieldMetadata> metadata = new LinkedHashMap<>();
        Set<String> requestedFields = new HashSet<>(spec.getFields() != null ? spec.getFields() : Collections.emptyList());
        if (requestedFields.isEmpty()) {
            extractedFieldMetadata = metadata;
            return metadata;
        }

        for (Object bodyDecl : originalTypeDecl.bodyDeclarations()) {
            if (!(bodyDecl instanceof FieldDeclaration)) {
                continue;
            }

            FieldDeclaration fieldDeclaration = (FieldDeclaration) bodyDecl;
            List<Modifier.ModifierKeyword> modifierKeywords = new ArrayList<>();
            for (Object modifierObj : fieldDeclaration.modifiers()) {
                if (modifierObj instanceof Modifier) {
                    Modifier modifier = (Modifier) modifierObj;
                    modifierKeywords.add(modifier.getKeyword());
                }
            }
            boolean isFinal = Modifier.isFinal(fieldDeclaration.getModifiers());
            boolean isStatic = Modifier.isStatic(fieldDeclaration.getModifiers());

            for (Object fragmentObj : fieldDeclaration.fragments()) {
                VariableDeclarationFragment fragment = (VariableDeclarationFragment) fragmentObj;
                String fieldName = fragment.getName().getIdentifier();

                if (!requestedFields.contains(fieldName)) {
                    continue;
                }

                Expression initializer = fragment.getInitializer();
                FieldMetadata info = new FieldMetadata(
                    fieldName,
                    fieldDeclaration.getType(),
                    isFinal,
                    isStatic,
                    modifierKeywords,
                    initializer
                );
                metadata.put(fieldName, info);
            }
        }

        extractedFieldMetadata = metadata;
        return metadata;
    }

    private Map<String, ExtractedFieldInfo> extractFields(AST targetAst, Set<String> fieldNames) {
        Map<String, ExtractedFieldInfo> result = new LinkedHashMap<>();
        Map<String, FieldMetadata> metadataMap = collectExtractedFieldMetadata();

        for (String fieldName : fieldNames) {
            FieldMetadata metadata = metadataMap.get(fieldName);
            if (metadata == null) {
                continue;
            }

            VariableDeclarationFragment fragment = targetAst.newVariableDeclarationFragment();
            fragment.setName(targetAst.newSimpleName(fieldName));
            if (metadata.initializer != null) {
                Expression initializerCopy = (Expression) ASTNode.copySubtree(targetAst, metadata.initializer);
                fragment.setInitializer(initializerCopy);
            }

            FieldDeclaration newField = targetAst.newFieldDeclaration(fragment);
            newField.setType((Type) ASTNode.copySubtree(targetAst, metadata.type));

            // For static fields, preserve original visibility; for instance fields, make private
            boolean visibilityAdded = false;
            if (metadata.isStatic) {
                // Preserve original visibility for static fields
                for (Modifier.ModifierKeyword keyword : metadata.otherModifiers) {
                    if (keyword == Modifier.ModifierKeyword.PUBLIC_KEYWORD
                        || keyword == Modifier.ModifierKeyword.PROTECTED_KEYWORD
                        || keyword == Modifier.ModifierKeyword.PRIVATE_KEYWORD) {
                        newField.modifiers().add(targetAst.newModifier(keyword));
                        visibilityAdded = true;
                        break;
                    }
                }
                // If no explicit visibility, static fields default to package-private (no modifier)
            } else {
                // Instance fields are always private in extracted class
                newField.modifiers().add(targetAst.newModifier(Modifier.ModifierKeyword.PRIVATE_KEYWORD));
                visibilityAdded = true;
            }

            // Add other modifiers (static, final, etc.)
            for (Modifier.ModifierKeyword keyword : metadata.otherModifiers) {
                if (keyword == Modifier.ModifierKeyword.PUBLIC_KEYWORD
                    || keyword == Modifier.ModifierKeyword.PROTECTED_KEYWORD
                    || keyword == Modifier.ModifierKeyword.PRIVATE_KEYWORD) {
                    continue;  // Already handled above
                }
                newField.modifiers().add(targetAst.newModifier(keyword));
            }

            ExtractedFieldInfo info = new ExtractedFieldInfo(
                fieldName,
                newField,
                metadata.isFinal,
                metadata.type
            );
            result.put(fieldName, info);
        }

        return result;
    }

    private void addFieldAccessors(AST targetAst, TypeDeclaration newClass, Map<String, ExtractedFieldInfo> extractedFields) {
        for (ExtractedFieldInfo info : extractedFields.values()) {
            MethodDeclaration getter = targetAst.newMethodDeclaration();
            getter.setName(targetAst.newSimpleName("get" + capitalize(info.name)));
            getter.modifiers().add(targetAst.newModifier(Modifier.ModifierKeyword.PUBLIC_KEYWORD));
            getter.setReturnType2((Type) ASTNode.copySubtree(targetAst, info.originalType));

            Block getterBody = targetAst.newBlock();
            ReturnStatement returnStatement = targetAst.newReturnStatement();
            FieldAccess returnExpression = targetAst.newFieldAccess();
            returnExpression.setExpression(targetAst.newThisExpression());
            returnExpression.setName(targetAst.newSimpleName(info.name));
            returnStatement.setExpression(returnExpression);
            getterBody.statements().add(returnStatement);
            getter.setBody(getterBody);

            newClass.bodyDeclarations().add(getter);

            MethodDeclaration setter = targetAst.newMethodDeclaration();
            setter.setName(targetAst.newSimpleName("set" + capitalize(info.name)));
            setter.modifiers().add(targetAst.newModifier(Modifier.ModifierKeyword.PUBLIC_KEYWORD));
            setter.setReturnType2(targetAst.newPrimitiveType(PrimitiveType.VOID));

            SingleVariableDeclaration parameter = targetAst.newSingleVariableDeclaration();
            parameter.setType((Type) ASTNode.copySubtree(targetAst, info.originalType));
            parameter.setName(targetAst.newSimpleName("value"));
            setter.parameters().add(parameter);

            Block setterBody = targetAst.newBlock();
            Assignment assignment = targetAst.newAssignment();
            FieldAccess leftHand = targetAst.newFieldAccess();
            leftHand.setExpression(targetAst.newThisExpression());
            leftHand.setName(targetAst.newSimpleName(info.name));
            assignment.setLeftHandSide(leftHand);
            assignment.setRightHandSide(targetAst.newSimpleName("value"));
            setterBody.statements().add(targetAst.newExpressionStatement(assignment));
            setter.setBody(setterBody);

            newClass.bodyDeclarations().add(setter);
            if (supportsIncrementOperations(info.originalType) && !info.isFinal) {
                addIncrementHelpers(targetAst, newClass, info);
            }
        }
    }

    /**
     * Extract methods from original class that should be moved to new class.
     */
    private List<MethodDeclaration> extractMethods(AST targetAst, Set<String> methodSignatures, Set<String> extractedFields) {
        List<MethodDeclaration> result = new ArrayList<>();

        for (Object bodyDecl : originalTypeDecl.bodyDeclarations()) {
            if (bodyDecl instanceof MethodDeclaration) {
                MethodDeclaration method = (MethodDeclaration) bodyDecl;
                String signature = getMethodSignature(method);

                if (methodSignatures.contains(signature)) {
                    // Copy the method to the new AST
                    MethodDeclaration copiedMethod = (MethodDeclaration) ASTNode.copySubtree(targetAst, method);
                    result.add(copiedMethod);
                }
            }
        }

        return result;
    }

    /**
     * Replace references to extracted fields with helper accessor calls.
     */
    private void replaceFieldReference(
        ASTRewrite rewrite,
        ASTNode fieldNode,
        String fieldName,
        String helperFieldName,
        Map<String, String> getterNames,
        Map<String, String> setterNames,
        Map<String, String> preIncrementNames,
        Map<String, String> postIncrementNames,
        Map<String, String> preDecrementNames,
        Map<String, String> postDecrementNames
    ) {
        ASTNode parent = fieldNode.getParent();

        if (parent instanceof Assignment) {
            Assignment assignment = (Assignment) parent;
            if (assignment.getLeftHandSide() != fieldNode) {
                MethodInvocation getterCall = createHelperInvocation(getterNames.get(fieldName), helperFieldName);
                if (getterCall != null) {
                    rewrite.replace(fieldNode, getterCall, null);
                }
                return;
            }

            String setterName = setterNames.get(fieldName);
            if (setterName == null) {
                return;
            }

            MethodInvocation setterCall = createHelperInvocation(setterName, helperFieldName);
            Expression rhs = (Expression) ASTNode.copySubtree(ast, assignment.getRightHandSide());

            if (assignment.getOperator() == Assignment.Operator.ASSIGN) {
                setterCall.arguments().add(rhs);
            } else {
                String getterName = getterNames.get(fieldName);
                InfixExpression.Operator mappedOperator = mapAssignmentOperator(assignment.getOperator());

                if (getterName != null && mappedOperator != null) {
                    MethodInvocation getterCall = createHelperInvocation(getterName, helperFieldName);
                    InfixExpression combined = ast.newInfixExpression();
                    combined.setOperator(mappedOperator);
                    combined.setLeftOperand(getterCall);
                    combined.setRightOperand(rhs);
                    setterCall.arguments().add(combined);
                } else {
                    setterCall.arguments().add(rhs);
                }
            }

            ASTNode assignmentParent = assignment.getParent();
            if (assignmentParent instanceof ExpressionStatement) {
                rewrite.replace(assignmentParent, ast.newExpressionStatement(setterCall), null);
            } else {
                rewrite.replace(assignment, setterCall, null);
            }
            return;
        }

        if (parent instanceof PostfixExpression) {
            PostfixExpression postfix = (PostfixExpression) parent;
            String methodName = postfix.getOperator() == PostfixExpression.Operator.INCREMENT
                ? postIncrementNames.get(fieldName)
                : postDecrementNames.get(fieldName);
            if (methodName == null) {
                return;
            }
            MethodInvocation helperCall = createHelperInvocation(methodName, helperFieldName);
            if (helperCall == null) {
                return;
            }
            if (postfix.getParent() instanceof ExpressionStatement) {
                rewrite.replace(postfix.getParent(), ast.newExpressionStatement(helperCall), null);
            } else {
                rewrite.replace(postfix, helperCall, null);
            }
            return;
        }

        if (parent instanceof PrefixExpression) {
            PrefixExpression prefix = (PrefixExpression) parent;
            String methodName = prefix.getOperator() == PrefixExpression.Operator.INCREMENT
                ? preIncrementNames.get(fieldName)
                : preDecrementNames.get(fieldName);
            if (methodName == null) {
                return;
            }
            MethodInvocation helperCall = createHelperInvocation(methodName, helperFieldName);
            if (helperCall == null) {
                return;
            }
            if (prefix.getParent() instanceof ExpressionStatement) {
                rewrite.replace(prefix.getParent(), ast.newExpressionStatement(helperCall), null);
            } else {
                rewrite.replace(prefix, helperCall, null);
            }
            return;
        }

        MethodInvocation getterCall = createHelperInvocation(getterNames.get(fieldName), helperFieldName);
        if (getterCall != null) {
            rewrite.replace(fieldNode, getterCall, null);
        }
    }

    private MethodInvocation createHelperInvocation(String methodName, String helperFieldName) {
        if (methodName == null) {
            return null;
        }
        MethodInvocation invocation = ast.newMethodInvocation();
        invocation.setExpression(ast.newSimpleName(helperFieldName));
        invocation.setName(ast.newSimpleName(methodName));
        return invocation;
    }

    private InfixExpression.Operator mapAssignmentOperator(Assignment.Operator operator) {
        if (operator == Assignment.Operator.PLUS_ASSIGN) {
            return InfixExpression.Operator.PLUS;
        } else if (operator == Assignment.Operator.MINUS_ASSIGN) {
            return InfixExpression.Operator.MINUS;
        } else if (operator == Assignment.Operator.TIMES_ASSIGN) {
            return InfixExpression.Operator.TIMES;
        } else if (operator == Assignment.Operator.DIVIDE_ASSIGN) {
            return InfixExpression.Operator.DIVIDE;
        } else if (operator == Assignment.Operator.REMAINDER_ASSIGN) {
            return InfixExpression.Operator.REMAINDER;
        } else if (operator == Assignment.Operator.LEFT_SHIFT_ASSIGN) {
            return InfixExpression.Operator.LEFT_SHIFT;
        } else if (operator == Assignment.Operator.RIGHT_SHIFT_SIGNED_ASSIGN) {
            return InfixExpression.Operator.RIGHT_SHIFT_SIGNED;
        } else if (operator == Assignment.Operator.RIGHT_SHIFT_UNSIGNED_ASSIGN) {
            return InfixExpression.Operator.RIGHT_SHIFT_UNSIGNED;
        } else if (operator == Assignment.Operator.BIT_AND_ASSIGN) {
            return InfixExpression.Operator.AND;
        } else if (operator == Assignment.Operator.BIT_OR_ASSIGN) {
            return InfixExpression.Operator.OR;
        } else if (operator == Assignment.Operator.BIT_XOR_ASSIGN) {
            return InfixExpression.Operator.XOR;
        }
        return null;
    }

    private boolean supportsIncrementOperations(Type type) {
        if (!(type instanceof PrimitiveType)) {
            return false;
        }
        PrimitiveType.Code code = ((PrimitiveType) type).getPrimitiveTypeCode();
        return code == PrimitiveType.INT
            || code == PrimitiveType.LONG
            || code == PrimitiveType.SHORT
            || code == PrimitiveType.BYTE
            || code == PrimitiveType.FLOAT
            || code == PrimitiveType.DOUBLE
            || code == PrimitiveType.CHAR;
    }

    private void addIncrementHelpers(AST targetAst, TypeDeclaration newClass, ExtractedFieldInfo info) {
        String capitalized = capitalize(info.name);

        MethodDeclaration prefixInc = targetAst.newMethodDeclaration();
        prefixInc.setName(targetAst.newSimpleName("increment" + capitalized));
        prefixInc.modifiers().add(targetAst.newModifier(Modifier.ModifierKeyword.PUBLIC_KEYWORD));
        prefixInc.setReturnType2((Type) ASTNode.copySubtree(targetAst, info.originalType));
        Block prefixIncBody = targetAst.newBlock();
        PrefixExpression prefixIncExpr = targetAst.newPrefixExpression();
        prefixIncExpr.setOperator(PrefixExpression.Operator.INCREMENT);
        prefixIncExpr.setOperand(createFieldAccess(targetAst, info.name));
        ReturnStatement prefixIncReturn = targetAst.newReturnStatement();
        prefixIncReturn.setExpression(prefixIncExpr);
        prefixIncBody.statements().add(prefixIncReturn);
        prefixInc.setBody(prefixIncBody);
        newClass.bodyDeclarations().add(prefixInc);

        MethodDeclaration postInc = targetAst.newMethodDeclaration();
        postInc.setName(targetAst.newSimpleName("postIncrement" + capitalized));
        postInc.modifiers().add(targetAst.newModifier(Modifier.ModifierKeyword.PUBLIC_KEYWORD));
        postInc.setReturnType2((Type) ASTNode.copySubtree(targetAst, info.originalType));
        Block postIncBody = targetAst.newBlock();
        ReturnStatement postIncReturn = targetAst.newReturnStatement();
        PostfixExpression postIncExpr = targetAst.newPostfixExpression();
        postIncExpr.setOperator(PostfixExpression.Operator.INCREMENT);
        postIncExpr.setOperand(createFieldAccess(targetAst, info.name));
        postIncReturn.setExpression(postIncExpr);
        postIncBody.statements().add(postIncReturn);
        postInc.setBody(postIncBody);
        newClass.bodyDeclarations().add(postInc);

        MethodDeclaration prefixDec = targetAst.newMethodDeclaration();
        prefixDec.setName(targetAst.newSimpleName("decrement" + capitalized));
        prefixDec.modifiers().add(targetAst.newModifier(Modifier.ModifierKeyword.PUBLIC_KEYWORD));
        prefixDec.setReturnType2((Type) ASTNode.copySubtree(targetAst, info.originalType));
        Block prefixDecBody = targetAst.newBlock();
        PrefixExpression prefixDecExpr = targetAst.newPrefixExpression();
        prefixDecExpr.setOperator(PrefixExpression.Operator.DECREMENT);
        prefixDecExpr.setOperand(createFieldAccess(targetAst, info.name));
        ReturnStatement prefixDecReturn = targetAst.newReturnStatement();
        prefixDecReturn.setExpression(prefixDecExpr);
        prefixDecBody.statements().add(prefixDecReturn);
        prefixDec.setBody(prefixDecBody);
        newClass.bodyDeclarations().add(prefixDec);

        MethodDeclaration postDec = targetAst.newMethodDeclaration();
        postDec.setName(targetAst.newSimpleName("postDecrement" + capitalized));
        postDec.modifiers().add(targetAst.newModifier(Modifier.ModifierKeyword.PUBLIC_KEYWORD));
        postDec.setReturnType2((Type) ASTNode.copySubtree(targetAst, info.originalType));
        Block postDecBody = targetAst.newBlock();
        ReturnStatement postDecReturn = targetAst.newReturnStatement();
        PostfixExpression postDecExpr = targetAst.newPostfixExpression();
        postDecExpr.setOperator(PostfixExpression.Operator.DECREMENT);
        postDecExpr.setOperand(createFieldAccess(targetAst, info.name));
        postDecReturn.setExpression(postDecExpr);
        postDecBody.statements().add(postDecReturn);
        postDec.setBody(postDecBody);
        newClass.bodyDeclarations().add(postDec);
    }

    private FieldAccess createFieldAccess(AST targetAst, String fieldName) {
        FieldAccess access = targetAst.newFieldAccess();
        access.setExpression(targetAst.newThisExpression());
        access.setName(targetAst.newSimpleName(fieldName));
        return access;
    }

    /**
     * Get method signature in format: methodName(Type1,Type2,...)
     */
    private String getMethodSignature(MethodDeclaration method) {
        StringBuilder sig = new StringBuilder();
        sig.append(method.getName().getIdentifier());
        sig.append("(");

        List<SingleVariableDeclaration> params = method.parameters();
        for (int i = 0; i < params.size(); i++) {
            if (i > 0) sig.append(",");
            SingleVariableDeclaration param = params.get(i);

            // Handle varargs: last parameter might be varargs
            if (param.isVarargs()) {
                // For varargs, append the type + "..."
                String typeStr = param.getType().toString();
                // Remove any existing [] from the type since varargs uses ...
                if (typeStr.endsWith("[]")) {
                    typeStr = typeStr.substring(0, typeStr.length() - 2);
                }
                sig.append(typeStr).append("...");
            } else {
                sig.append(param.getType().toString());
            }
        }

        sig.append(")");
        return sig.toString();
    }

    /**
     * Normalize method signatures from GenEC format to internal format.
     * GenEC may send signatures like "methodName(Type1,Type2)" or "methodName(Type1 param1, Type2 param2)"
     * Also handles array notation differences: byte vs byte[], String... vs String[]
     */
    private Set<String> normalizeMethodSignatures(List<String> methodSigs) {
        Set<String> normalized = new HashSet<>();

        for (String sig : methodSigs) {
            // Remove parameter names if present
            // Example: "method(String name, int age)" -> "method(String,int)"
            String normalized_sig = sig.replaceAll("\\s*\\w+\\s*(?=[,)])", "");
            normalized.add(normalized_sig);

            // Also add the original in case it's already normalized
            normalized.add(sig);

            // Create variant with [] stripped from arrays (javalang sometimes omits [])
            // "method(byte[],int)" -> also match "method(byte,int)"
            String arrayStripped = normalized_sig.replaceAll("\\[\\]", "");
            if (!arrayStripped.equals(normalized_sig)) {
                normalized.add(arrayStripped);
            }

            // Create variant with [] added to potential array types before comma or )
            // This handles case where Python sends "byte" but Java has "byte[]"
            // Match word characters followed by comma or closing paren, add []
            String withArrays = normalized_sig.replaceAll("\\b(byte|char|short|int|long|float|double|boolean)(?=[,)])", "$1[]");
            if (!withArrays.equals(normalized_sig)) {
                normalized.add(withArrays);
            }

            // Also handle varargs: String... <-> String[]
            String varargsToArray = normalized_sig.replace("...", "[]");
            if (!varargsToArray.equals(normalized_sig)) {
                normalized.add(varargsToArray);
            }

            String arrayToVarargs = normalized_sig.replace("[]", "...");
            if (!arrayToVarargs.equals(normalized_sig)) {
                normalized.add(arrayToVarargs);
            }
        }

        return normalized;
    }

    /**
     * Convert class name to camelCase for field naming.
     */
    private String toCamelCase(String name) {
        if (name == null || name.isEmpty()) {
            return name;
        }
        return Character.toLowerCase(name.charAt(0)) + name.substring(1);
    }

    private String capitalize(String name) {
        if (name == null || name.isEmpty()) {
            return name;
        }
        return Character.toUpperCase(name.charAt(0)) + name.substring(1);
    }

    /**
     * Compute the file path for the new extracted class.
     */
    private String computeNewClassPath() {
        String originalPath = spec.getClassFile();
        String directory = originalPath.substring(0, originalPath.lastIndexOf(File.separator));
        return directory + File.separator + spec.getNewClassName() + ".java";
    }

    /**
     * Read file contents.
     */
    private String readFile(String filePath) throws IOException {
        return new String(Files.readAllBytes(Paths.get(filePath)));
    }

    /**
     * Get stack trace as string.
     */
    private String getStackTrace(Exception e) {
        StringBuilder sb = new StringBuilder();
        for (StackTraceElement element : e.getStackTrace()) {
            sb.append("  at ").append(element.toString()).append("\n");
        }
        return sb.toString();
    }
}
