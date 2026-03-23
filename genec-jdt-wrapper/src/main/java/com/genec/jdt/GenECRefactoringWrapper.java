package com.genec.jdt;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;

/**
 * Main wrapper class for Eclipse JDT-based refactoring.
 *
 * This class serves as the bridge between GenEC (Python) and Eclipse JDT (Java).
 * It receives refactoring specifications as JSON, executes the Extract Class
 * refactoring using Eclipse JDT, and returns the results as JSON.
 *
 * Usage:
 *   java -jar genec-jdt-wrapper.jar --spec '{...json...}'
 *
 * @author GenEC Team
 */
public class GenECRefactoringWrapper {

    private static final Gson gson = new GsonBuilder().setPrettyPrinting().create();

    public static void main(String[] args) {
        try {
            // Parse command line arguments
            RefactoringSpec spec = parseArguments(args);

            // Execute refactoring
            RefactoringResult result = performRefactoring(spec);

            // Output result as JSON
            String jsonResult = gson.toJson(result);
            System.out.println(jsonResult);

            // Exit with appropriate code
            System.exit(result.isSuccess() ? 0 : 1);

        } catch (Exception e) {
            // Error handling - return error as JSON
            RefactoringResult errorResult = new RefactoringResult(
                false,
                "Error: " + e.getMessage() + "\n" + getStackTrace(e)
            );
            System.err.println(gson.toJson(errorResult));
            System.exit(1);
        }
    }

    /**
     * Parse command line arguments to extract refactoring specification.
     *
     * Expected format: --spec '{...json...}'
     */
    private static RefactoringSpec parseArguments(String[] args) throws IllegalArgumentException {
        if (args.length < 2) {
            throw new IllegalArgumentException(
                "Usage: java -jar genec-jdt-wrapper.jar --spec '{...json...}'"
            );
        }

        String specJson = null;
        for (int i = 0; i < args.length; i++) {
            if ("--spec".equals(args[i]) && i + 1 < args.length) {
                specJson = args[i + 1];
                break;
            }
        }

        if (specJson == null || specJson.isEmpty()) {
            throw new IllegalArgumentException("Missing --spec argument");
        }

        try {
            RefactoringSpec spec = gson.fromJson(specJson, RefactoringSpec.class);
            validateSpec(spec);
            return spec;
        } catch (Exception e) {
            throw new IllegalArgumentException("Invalid JSON specification: " + e.getMessage(), e);
        }
    }

    /**
     * Validate refactoring specification.
     */
    private static void validateSpec(RefactoringSpec spec) throws IllegalArgumentException {
        if (spec.getProjectPath() == null || spec.getProjectPath().isEmpty()) {
            throw new IllegalArgumentException("Project path is required");
        }
        if (spec.getClassFile() == null || spec.getClassFile().isEmpty()) {
            throw new IllegalArgumentException("Class file is required");
        }
        if (spec.getNewClassName() == null || spec.getNewClassName().isEmpty()) {
            throw new IllegalArgumentException("New class name is required");
        }
        // Validate class name is a valid Java identifier
        String className = spec.getNewClassName();
        if (!Character.isJavaIdentifierStart(className.charAt(0))) {
            throw new IllegalArgumentException("Invalid class name (must start with letter, _ or $): " + className);
        }
        for (int i = 1; i < className.length(); i++) {
            if (!Character.isJavaIdentifierPart(className.charAt(i))) {
                throw new IllegalArgumentException("Invalid character in class name at position " + i + ": " + className);
            }
        }
        if (spec.getMethods() == null || spec.getMethods().isEmpty()) {
            throw new IllegalArgumentException("At least one method is required");
        }
    }

    /**
     * Perform Extract Class refactoring using Eclipse JDT.
     *
     * This implementation:
     * 1. Parses Java file with JDT AST
     * 2. Extracts specified methods and fields
     * 3. Generates new extracted class
     * 4. Modifies original class (removes extracted members)
     * 5. Returns generated code
     */
    private static RefactoringResult performRefactoring(RefactoringSpec spec) {
        // Delegate to the actual JDT refactoring implementation
        EclipseJDTRefactoring refactoring = new EclipseJDTRefactoring(spec);
        return refactoring.execute();
    }

    /**
     * Get stack trace as string.
     */
    private static String getStackTrace(Exception e) {
        StringBuilder sb = new StringBuilder();
        for (StackTraceElement element : e.getStackTrace()) {
            sb.append("  at ").append(element.toString()).append("\n");
        }
        return sb.toString();
    }
}
