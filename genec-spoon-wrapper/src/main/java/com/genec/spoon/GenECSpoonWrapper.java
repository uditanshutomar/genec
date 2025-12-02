package com.genec.spoon;

import spoon.Launcher;
import spoon.reflect.declaration.*;
import spoon.reflect.reference.CtExecutableReference;
import spoon.reflect.reference.CtFieldReference;
import spoon.reflect.code.*;
import spoon.reflect.visitor.filter.TypeFilter;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.util.*;

/**
 * Spoon wrapper for GenEC dependency analysis.
 *
 * This wrapper provides comprehensive Java dependency analysis using
 * the Spoon metaprogramming library from INRIA.
 */
public class GenECSpoonWrapper {

    public static void main(String[] args) {
        if (args.length < 2 || !args[0].equals("--spec")) {
            System.err.println("Usage: java -jar genec-spoon-wrapper.jar --spec <json-spec>");
            System.exit(1);
        }

        String specJson = args[1];
        Gson gson = new GsonBuilder().setPrettyPrinting().create();

        try {
            // Parse specification
            @SuppressWarnings("unchecked")
            Map<String, Object> spec = gson.fromJson(specJson, Map.class);
            String classFile = (String) spec.get("classFile");

            if (classFile == null || classFile.isEmpty()) {
                throw new IllegalArgumentException("classFile is required in specification");
            }

            // Create Spoon launcher
            Launcher launcher = new Launcher();
            launcher.addInputResource(classFile);
            launcher.getEnvironment().setNoClasspath(true);
            launcher.getEnvironment().setComplianceLevel(11);
            launcher.getEnvironment().setCommentEnabled(false);
            launcher.buildModel();

            // Analyze class
            Map<String, Object> result = analyzeClass(launcher);
            result.put("success", true);
            result.put("message", "Analysis completed successfully");

            // Output JSON result
            System.out.println(gson.toJson(result));

        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("success", false);
            error.put("message", "Analysis failed: " + e.getMessage());
            error.put("error", e.getClass().getSimpleName());
            System.err.println(gson.toJson(error));
            System.exit(1);
        }
    }

    private static Map<String, Object> analyzeClass(Launcher launcher) {
        Map<String, Object> result = new HashMap<>();

        // Get all classes
        List<CtType<?>> types = launcher.getModel().getElements(new TypeFilter<>(CtType.class));

        if (types.isEmpty()) {
            throw new RuntimeException("No classes found in source file");
        }

        // Analyze first class (main class in file)
        CtType<?> mainClass = types.get(0);

        result.put("className", mainClass.getSimpleName());
        result.put("packageName", mainClass.getPackage() != null ?
                   mainClass.getPackage().getQualifiedName() : "");

        // Extract methods
        List<Map<String, Object>> methods = new ArrayList<>();
        Map<String, List<String>> methodCalls = new HashMap<>();
        Map<String, List<String>> fieldAccesses = new HashMap<>();

        for (CtMethod<?> method : mainClass.getMethods()) {
            Map<String, Object> methodInfo = extractMethodInfo(method);
            methods.add(methodInfo);

            // Extract method calls and field accesses
            String signature = (String) methodInfo.get("signature");
            methodCalls.put(signature, extractMethodCalls(method, mainClass));
            fieldAccesses.put(signature, extractFieldAccesses(method, mainClass));
        }
        result.put("methods", methods);

        // Extract constructors - using getElements with TypeFilter
        List<Map<String, Object>> constructors = new ArrayList<>();
        List<CtConstructor<?>> ctorList = mainClass.getElements(new TypeFilter<>(CtConstructor.class));
        for (CtConstructor<?> ctor : ctorList) {
            Map<String, Object> ctorInfo = extractConstructorInfo(ctor);
            constructors.add(ctorInfo);

            // Extract method calls and field accesses for constructors
            String signature = (String) ctorInfo.get("signature");
            methodCalls.put(signature, extractMethodCalls(ctor, mainClass));
            fieldAccesses.put(signature, extractFieldAccesses(ctor, mainClass));
        }
        result.put("constructors", constructors);

        // Extract fields
        List<Map<String, Object>> fields = new ArrayList<>();
        for (CtField<?> field : mainClass.getFields()) {
            Map<String, Object> fieldInfo = new HashMap<>();
            fieldInfo.put("name", field.getSimpleName());
            fieldInfo.put("type", field.getType().getSimpleName());
            fieldInfo.put("modifiers", getModifiers(field));
            fieldInfo.put("lineNumber", field.getPosition() != null ?
                         field.getPosition().getLine() : 0);
            fields.add(fieldInfo);
        }
        result.put("fields", fields);

        // Add dependency information
        result.put("methodCalls", methodCalls);
        result.put("fieldAccesses", fieldAccesses);

        return result;
    }

    private static Map<String, Object> extractMethodInfo(CtMethod<?> method) {
        Map<String, Object> methodInfo = new HashMap<>();
        methodInfo.put("name", method.getSimpleName());
        methodInfo.put("signature", buildMethodSignature(method));
        methodInfo.put("returnType", method.getType().getSimpleName());
        methodInfo.put("modifiers", getModifiers(method));
        methodInfo.put("parameters", getParameters(method));
        methodInfo.put("startLine", method.getPosition() != null ?
                      method.getPosition().getLine() : 0);
        methodInfo.put("endLine", method.getPosition() != null ?
                      method.getPosition().getEndLine() : 0);
        methodInfo.put("body", method.getBody() != null ?
                      method.getBody().toString() : "");
        return methodInfo;
    }

    private static Map<String, Object> extractConstructorInfo(CtConstructor<?> ctor) {
        Map<String, Object> ctorInfo = new HashMap<>();
        ctorInfo.put("name", ctor.getSimpleName());
        ctorInfo.put("signature", buildConstructorSignature(ctor));
        ctorInfo.put("modifiers", getModifiers(ctor));
        ctorInfo.put("parameters", getParameters(ctor));
        ctorInfo.put("startLine", ctor.getPosition() != null ?
                    ctor.getPosition().getLine() : 0);
        ctorInfo.put("endLine", ctor.getPosition() != null ?
                    ctor.getPosition().getEndLine() : 0);
        ctorInfo.put("body", ctor.getBody() != null ?
                    ctor.getBody().toString() : "");
        return ctorInfo;
    }

    private static String buildMethodSignature(CtMethod<?> method) {
        StringBuilder sig = new StringBuilder();
        sig.append(method.getSimpleName()).append("(");

        List<CtParameter<?>> params = method.getParameters();
        for (int i = 0; i < params.size(); i++) {
            if (i > 0) sig.append(",");
            sig.append(params.get(i).getType().getSimpleName());
        }
        sig.append(")");
        return sig.toString();
    }

    private static String buildConstructorSignature(CtConstructor<?> ctor) {
        StringBuilder sig = new StringBuilder();
        sig.append(ctor.getSimpleName()).append("(");

        List<CtParameter<?>> params = ctor.getParameters();
        for (int i = 0; i < params.size(); i++) {
            if (i > 0) sig.append(",");
            sig.append(params.get(i).getType().getSimpleName());
        }
        sig.append(")");
        return sig.toString();
    }

    private static List<String> extractMethodCalls(CtExecutable<?> executable, CtType<?> mainClass) {
        Set<String> calls = new HashSet<>();

        if (executable.getBody() == null) {
            return new ArrayList<>(calls);
        }

        // Get all method invocations in the body
        List<CtInvocation<?>> invocations = executable.getBody()
            .getElements(new TypeFilter<>(CtInvocation.class));

        // Get all method names in the main class
        Set<String> classMethodNames = new HashSet<>();
        for (CtMethod<?> m : mainClass.getMethods()) {
            classMethodNames.add(m.getSimpleName());
        }

        // Check for constructor chaining
        List<CtConstructorCall<?>> constructorCalls = executable.getBody()
            .getElements(new TypeFilter<>(CtConstructorCall.class));

        for (CtConstructorCall<?> call : constructorCalls) {
            // Check if it's calling the same class constructor
            if (call.getType() != null &&
                call.getType().getSimpleName().equals(mainClass.getSimpleName())) {
                calls.add(mainClass.getSimpleName());
            }
        }

        // Extract method calls
        for (CtInvocation<?> invocation : invocations) {
            CtExecutableReference<?> execRef = invocation.getExecutable();
            String methodName = execRef.getSimpleName();

            // Only include methods that are in this class
            if (classMethodNames.contains(methodName)) {
                calls.add(methodName);
            }
        }

        return new ArrayList<>(calls);
    }

    private static List<String> extractFieldAccesses(CtExecutable<?> executable, CtType<?> mainClass) {
        Set<String> accesses = new HashSet<>();

        if (executable.getBody() == null) {
            return new ArrayList<>(accesses);
        }

        // Get all field names in the main class
        Set<String> classFieldNames = new HashSet<>();
        for (CtField<?> f : mainClass.getFields()) {
            classFieldNames.add(f.getSimpleName());
        }

        // Get all field reads
        List<CtFieldRead<?>> fieldReads = executable.getBody()
            .getElements(new TypeFilter<>(CtFieldRead.class));

        for (CtFieldRead<?> read : fieldReads) {
            String fieldName = read.getVariable().getSimpleName();
            if (classFieldNames.contains(fieldName)) {
                accesses.add(fieldName);
            }
        }

        // Get all field writes
        List<CtFieldWrite<?>> fieldWrites = executable.getBody()
            .getElements(new TypeFilter<>(CtFieldWrite.class));

        for (CtFieldWrite<?> write : fieldWrites) {
            String fieldName = write.getVariable().getSimpleName();
            if (classFieldNames.contains(fieldName)) {
                accesses.add(fieldName);
            }
        }

        return new ArrayList<>(accesses);
    }

    private static List<String> getModifiers(CtModifiable element) {
        List<String> modifiers = new ArrayList<>();
        if (element.isPublic()) modifiers.add("public");
        if (element.isPrivate()) modifiers.add("private");
        if (element.isProtected()) modifiers.add("protected");
        if (element.isStatic()) modifiers.add("static");
        if (element.isFinal()) modifiers.add("final");
        if (element instanceof CtMethod && ((CtMethod<?>) element).isAbstract()) {
            modifiers.add("abstract");
        }
        return modifiers;
    }

    private static List<Map<String, Object>> getParameters(CtExecutable<?> executable) {
        List<Map<String, Object>> params = new ArrayList<>();
        for (CtParameter<?> param : executable.getParameters()) {
            Map<String, Object> paramInfo = new HashMap<>();
            paramInfo.put("name", param.getSimpleName());
            paramInfo.put("type", param.getType().getSimpleName());
            params.add(paramInfo);
        }
        return params;
    }
}
