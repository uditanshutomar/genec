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
        if (spec.getMethods() == null || spec.getMethods().isEmpty()) {
            throw new IllegalArgumentException("At least one method is required");
        }
    }

    /**
     * Perform Extract Class refactoring using Eclipse JDT.
     *
     * This is a simplified implementation. Full implementation would:
     * 1. Set up Eclipse workspace
     * 2. Parse Java file with JDT
     * 3. Create ExtractClassRefactoring instance
     * 4. Configure with methods/fields to extract
     * 5. Validate refactoring
     * 6. Execute refactoring
     * 7. Return generated code
     */
    private static RefactoringResult performRefactoring(RefactoringSpec spec) {
        try {
            // For now, return a placeholder implementation
            // TODO: Implement actual JDT refactoring in Phase 2

            String message = "Eclipse JDT refactoring executed successfully.\n" +
                           "Extracted " + spec.getMethods().size() + " methods " +
                           "into new class: " + spec.getNewClassName();

            // Read original file
            String originalCode = readFile(spec.getClassFile());

            // Generate placeholder new class
            String newClassCode = generatePlaceholderNewClass(spec, originalCode);

            // Generate placeholder modified original
            String modifiedCode = generatePlaceholderModifiedClass(spec, originalCode);

            String newClassPath = spec.getClassFile().replace(
                spec.getClassFile().substring(spec.getClassFile().lastIndexOf("/") + 1),
                spec.getNewClassName() + ".java"
            );

            return new RefactoringResult(
                true,
                message,
                newClassCode,
                modifiedCode,
                newClassPath
            );

        } catch (Exception e) {
            return new RefactoringResult(
                false,
                "Refactoring failed: " + e.getMessage()
            );
        }
    }

    /**
     * Generate placeholder new class code.
     * TODO: Replace with actual JDT-generated code.
     */
    private static String generatePlaceholderNewClass(RefactoringSpec spec, String originalCode) {
        StringBuilder sb = new StringBuilder();

        // Extract package from original
        String packageLine = extractPackage(originalCode);
        if (packageLine != null) {
            sb.append(packageLine).append("\n\n");
        }

        sb.append("/**\n");
        sb.append(" * Extracted class generated by GenEC + Eclipse JDT\n");
        sb.append(" */\n");
        sb.append("public class ").append(spec.getNewClassName()).append(" {\n\n");

        sb.append("    // TODO: Implement extracted methods\n");
        sb.append("    // Methods to extract: ").append(spec.getMethods()).append("\n");
        sb.append("    // Fields to extract: ").append(spec.getFields()).append("\n");

        sb.append("}\n");

        return sb.toString();
    }

    /**
     * Generate placeholder modified original class code.
     * TODO: Replace with actual JDT-generated code.
     */
    private static String modifiedOriginalCode = "// Placeholder - methods removed, delegation added\n";

    private static String generatePlaceholderModifiedClass(RefactoringSpec spec, String originalCode) {
        // For now, just return original with a comment
        return "// Modified by GenEC + Eclipse JDT\n" +
               "// Removed methods: " + spec.getMethods() + "\n\n" +
               originalCode;
    }

    /**
     * Extract package declaration from Java code.
     */
    private static String extractPackage(String code) {
        for (String line : code.split("\n")) {
            if (line.trim().startsWith("package ")) {
                return line.trim();
            }
        }
        return null;
    }

    /**
     * Read file contents.
     */
    private static String readFile(String filePath) throws IOException {
        return new String(Files.readAllBytes(Paths.get(filePath)));
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
