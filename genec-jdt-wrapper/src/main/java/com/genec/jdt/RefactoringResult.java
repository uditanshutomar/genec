package com.genec.jdt;

/**
 * Result of Extract Class refactoring execution.
 *
 * This class represents the output that will be sent back to GenEC's Python code,
 * containing the generated code for the new class and the modified original class.
 */
public class RefactoringResult {
    private boolean success;
    private String message;
    private String newClassCode;
    private String modifiedOriginalCode;
    private String newClassPath;

    public RefactoringResult(boolean success, String message) {
        this.success = success;
        this.message = message;
    }

    public RefactoringResult(boolean success, String message, String newClassCode, String modifiedOriginalCode, String newClassPath) {
        this.success = success;
        this.message = message;
        this.newClassCode = newClassCode;
        this.modifiedOriginalCode = modifiedOriginalCode;
        this.newClassPath = newClassPath;
    }

    // Getters and Setters
    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getNewClassCode() {
        return newClassCode;
    }

    public void setNewClassCode(String newClassCode) {
        this.newClassCode = newClassCode;
    }

    public String getModifiedOriginalCode() {
        return modifiedOriginalCode;
    }

    public void setModifiedOriginalCode(String modifiedOriginalCode) {
        this.modifiedOriginalCode = modifiedOriginalCode;
    }

    public String getNewClassPath() {
        return newClassPath;
    }

    public void setNewClassPath(String newClassPath) {
        this.newClassPath = newClassPath;
    }
}
