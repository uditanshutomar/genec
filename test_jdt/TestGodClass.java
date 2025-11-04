package com.example.test;

/**
 * Test god class for JDT refactoring
 */
public class TestGodClass {

    // Fields
    private String accountNumber;
    private double balance;
    private String customerName;
    private String address;

    // Constructor
    public TestGodClass(String accountNumber, String customerName) {
        this.accountNumber = accountNumber;
        this.customerName = customerName;
        this.balance = 0.0;
    }

    // Account-related methods (should be extracted)
    public void deposit(double amount) {
        if (amount > 0) {
            balance += amount;
            System.out.println("Deposited: " + amount);
        }
    }

    public void withdraw(double amount) {
        if (amount > 0 && balance >= amount) {
            balance -= amount;
            System.out.println("Withdrawn: " + amount);
        }
    }

    public double getBalance() {
        return balance;
    }

    // Customer-related methods (should remain)
    public String getCustomerName() {
        return customerName;
    }

    public void setAddress(String address) {
        this.address = address;
    }

    public String getAddress() {
        return address;
    }
}
