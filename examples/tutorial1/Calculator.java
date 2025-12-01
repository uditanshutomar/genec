package com.example;

public class Calculator {
    private int lastResult;

    // Basic arithmetic operations
    public int add(int a, int b) {
        lastResult = a + b;
        logOperation("ADD");
        return lastResult;
    }

    public int subtract(int a, int b) {
        lastResult = a - b;
        logOperation("SUBTRACT");
        return lastResult;
    }

    public int multiply(int a, int b) {
        lastResult = a * b;
        logOperation("MULTIPLY");
        return lastResult;
    }

    // Logging methods - candidate for extraction
    private void logOperation(String operation) {
        System.out.println("Operation: " + operation);
        logTimestamp();
    }

    private void logTimestamp() {
        System.out.println("Time: " + System.currentTimeMillis());
    }

    public void printLog() {
        System.out.println("Last result: " + lastResult);
    }

    public int getLastResult() {
        return lastResult;
    }
}
