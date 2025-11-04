package com.genec.jdt;

import java.util.List;

/**
 * Specification for Extract Class refactoring from GenEC.
 *
 * This class represents the input from GenEC's Python code,
 * containing information about what cluster to extract and
 * what the new class should be called.
 */
public class RefactoringSpec {
    private String projectPath;
    private String classFile;
    private String newClassName;
    private List<String> methods;
    private List<String> fields;

    // Getters and Setters
    public String getProjectPath() {
        return projectPath;
    }

    public void setProjectPath(String projectPath) {
        this.projectPath = projectPath;
    }

    public String getClassFile() {
        return classFile;
    }

    public void setClassFile(String classFile) {
        this.classFile = classFile;
    }

    public String getNewClassName() {
        return newClassName;
    }

    public void setNewClassName(String newClassName) {
        this.newClassName = newClassName;
    }

    public List<String> getMethods() {
        return methods;
    }

    public void setMethods(List<String> methods) {
        this.methods = methods;
    }

    public List<String> getFields() {
        return fields;
    }

    public void setFields(List<String> fields) {
        this.fields = fields;
    }

    @Override
    public String toString() {
        return "RefactoringSpec{" +
                "projectPath='" + projectPath + '\'' +
                ", classFile='" + classFile + '\'' +
                ", newClassName='" + newClassName + '\'' +
                ", methods=" + methods +
                ", fields=" + fields +
                '}';
    }
}
