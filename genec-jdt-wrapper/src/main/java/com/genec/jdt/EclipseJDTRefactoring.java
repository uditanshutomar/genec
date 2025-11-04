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
        final List<Modifier.ModifierKeyword> otherModifiers;
        final Expression initializer;

        FieldMetadata(String name, Type type, boolean isFinal,
                      List<Modifier.ModifierKeyword> otherModifiers,
                      Expression initializer) {
            this.name = name;
            this.type = type;
            this.isFinal = isFinal;
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
        Set<String> methodSignatures = normalizeMethodSignatures(spec.getMethods());
        List<MethodDeclaration> extractedMethods = extractMethods(newAst, methodSignatures, extractedFields.keySet());
        for (MethodDeclaration method : extractedMethods) {
            newClass.bodyDeclarations().add(method);
        }

        // Add accessors for extracted fields to maintain encapsulation
        addFieldAccessors(newAst, newClass, extractedFields);

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
        for (Object bodyDecl : originalTypeDecl.bodyDeclarations()) {
            if (bodyDecl instanceof MethodDeclaration) {
                MethodDeclaration method = (MethodDeclaration) bodyDecl;
                String signature = getMethodSignature(method);
                if (methodSignatures.contains(signature)) {
                    Block newBody = ast.newBlock();

                    MethodInvocation invocation = ast.newMethodInvocation();
                    invocation.setExpression(ast.newSimpleName(helperFieldName));
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
        for (String fieldName : fieldNames) {
            FieldMetadata metadata = fieldMetadata.get(fieldName);
            if (metadata == null) {
                continue;
            }
            getterNames.put(fieldName, "get" + capitalize(fieldName));
            if (!metadata.isFinal) {
                setterNames.put(fieldName, "set" + capitalize(fieldName));
            }
        }

        final Set<String> extractedFieldNames = new HashSet<>(fieldNames);

        if (!extractedFieldNames.isEmpty()) {
            originalTypeDecl.accept(new ASTVisitor() {
                @Override
                public boolean visit(SimpleName node) {
                    String identifier = node.getIdentifier();
                    if (!extractedFieldNames.contains(identifier)) {
                        return true;
                    }
                    replaceFieldReference(rewrite, node, identifier, helperFieldName, getterNames, setterNames);
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
                    replaceFieldReference(rewrite, node, identifier, helperFieldName, getterNames, setterNames);
                    return false;
                }
            });
        }

        // Add field for the extracted class instance
        VariableDeclarationFragment fragment = ast.newVariableDeclarationFragment();
        fragment.setName(ast.newSimpleName(toCamelCase(spec.getNewClassName())));

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

        // Apply changes to document
        Document document = new Document(originalSource);
        TextEdit edits = rewrite.rewriteAST(document, null);
        edits.apply(document);

        return document.get();
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
            newField.modifiers().add(targetAst.newModifier(Modifier.ModifierKeyword.PRIVATE_KEYWORD));

            for (Modifier.ModifierKeyword keyword : metadata.otherModifiers) {
                if (keyword == Modifier.ModifierKeyword.PUBLIC_KEYWORD
                    || keyword == Modifier.ModifierKeyword.PROTECTED_KEYWORD
                    || keyword == Modifier.ModifierKeyword.PRIVATE_KEYWORD) {
                    continue;
                }
                if (keyword == Modifier.ModifierKeyword.FINAL_KEYWORD && metadata.isFinal) {
                    newField.modifiers().add(targetAst.newModifier(Modifier.ModifierKeyword.FINAL_KEYWORD));
                    continue;
                }
                if (keyword != Modifier.ModifierKeyword.FINAL_KEYWORD) {
                    newField.modifiers().add(targetAst.newModifier(keyword));
                }
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

            if (info.isFinal) {
                continue;
            }

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
        Map<String, String> setterNames
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
            String setterName = setterNames.get(fieldName);
            String getterName = getterNames.get(fieldName);
            if (setterName == null || getterName == null) {
                return;
            }
            MethodInvocation getterCall = createHelperInvocation(getterName, helperFieldName);
            InfixExpression delta = ast.newInfixExpression();
            delta.setLeftOperand(getterCall);
            delta.setRightOperand(ast.newNumberLiteral("1"));
            delta.setOperator(
                postfix.getOperator() == PostfixExpression.Operator.INCREMENT
                    ? InfixExpression.Operator.PLUS
                    : InfixExpression.Operator.MINUS
            );

            MethodInvocation setterCall = createHelperInvocation(setterName, helperFieldName);
            setterCall.arguments().add(delta);

            if (postfix.getParent() instanceof ExpressionStatement) {
                rewrite.replace(postfix.getParent(), ast.newExpressionStatement(setterCall), null);
            } else {
                rewrite.replace(postfix, setterCall, null);
            }
            return;
        }

        if (parent instanceof PrefixExpression) {
            PrefixExpression prefix = (PrefixExpression) parent;
            String setterName = setterNames.get(fieldName);
            String getterName = getterNames.get(fieldName);
            if (setterName == null || getterName == null) {
                return;
            }

            MethodInvocation getterCall = createHelperInvocation(getterName, helperFieldName);
            InfixExpression delta = ast.newInfixExpression();
            delta.setLeftOperand(getterCall);
            delta.setRightOperand(ast.newNumberLiteral("1"));
            delta.setOperator(
                prefix.getOperator() == PrefixExpression.Operator.INCREMENT
                    ? InfixExpression.Operator.PLUS
                    : InfixExpression.Operator.MINUS
            );

            MethodInvocation setterCall = createHelperInvocation(setterName, helperFieldName);
            setterCall.arguments().add(delta);

            if (prefix.getParent() instanceof ExpressionStatement) {
                rewrite.replace(prefix.getParent(), ast.newExpressionStatement(setterCall), null);
            } else {
                rewrite.replace(prefix, setterCall, null);
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
            sig.append(params.get(i).getType().toString());
        }

        sig.append(")");
        return sig.toString();
    }

    /**
     * Normalize method signatures from GenEC format to internal format.
     * GenEC may send signatures like "methodName(Type1,Type2)" or "methodName(Type1 param1, Type2 param2)"
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
