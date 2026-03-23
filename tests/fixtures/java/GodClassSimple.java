package com.test;

/**
 * A God Class with three clear responsibilities:
 * 1. User management (user-related fields and methods)
 * 2. Account/balance operations
 * 3. Notification/email operations
 */
public class GodClassSimple {
    // User fields
    private String userName;
    private int userAge;

    // Account fields
    private double balance;
    private String accountId;

    // Notification fields
    private String email;
    private boolean notificationsEnabled;

    // === User Management ===
    public String getUserName() { return userName; }
    public void setUserName(String name) { this.userName = name; }
    public int getUserAge() { return userAge; }
    public void setUserAge(int age) { this.userAge = age; }
    public boolean isAdult() { return userAge >= 18; }
    public String getUserInfo() { return userName + " (age: " + userAge + ")"; }

    // === Account Operations ===
    public double getBalance() { return balance; }
    public void setBalance(double b) { this.balance = b; }
    public String getAccountId() { return accountId; }
    public void deposit(double amount) {
        if (amount <= 0) throw new IllegalArgumentException("Amount must be positive");
        balance += amount;
    }
    public void withdraw(double amount) {
        if (amount > balance) throw new IllegalArgumentException("Insufficient funds");
        balance -= amount;
    }
    public boolean hasEnoughFunds(double amount) { return balance >= amount; }
    public String getAccountSummary() { return accountId + ": $" + balance; }

    // === Notification Operations ===
    public String getEmail() { return email; }
    public void setEmail(String e) { this.email = e; }
    public boolean isNotificationsEnabled() { return notificationsEnabled; }
    public void enableNotifications() { this.notificationsEnabled = true; }
    public void disableNotifications() { this.notificationsEnabled = false; }
    public boolean isValidEmail() { return email != null && email.contains("@"); }
    public void sendNotification(String message) {
        if (notificationsEnabled && isValidEmail()) {
            System.out.println("To: " + email + " - " + message);
        }
    }
    public void notifyBalanceChange() {
        sendNotification("Balance updated: $" + balance);
    }
}
