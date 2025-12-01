package com.example;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

public class UserManager {
    private List<User> users = new ArrayList<>();
    private static final Pattern EMAIL_PATTERN =
        Pattern.compile("^[A-Za-z0-9+_.-]+@(.+)$");

    // Data access methods
    public User findById(int id) {
        for (User user : users) {
            if (user.getId() == id) {
                return user;
            }
        }
        return null;
    }

    public List<User> findAll() {
        return new ArrayList<>(users);
    }

    public void save(User user) {
        users.add(user);
    }

    public void delete(int id) {
        users.removeIf(u -> u.getId() == id);
    }

    // Validation methods
    public boolean validateEmail(String email) {
        return email != null && EMAIL_PATTERN.matcher(email).matches();
    }

    public boolean validateUsername(String username) {
        return username != null &&
               username.length() >= 3 &&
               username.length() <= 20;
    }

    public boolean validateAge(int age) {
        return age >= 0 && age <= 150;
    }

    // Business logic
    public User createUser(String username, String email, int age) {
        if (!validateUsername(username)) {
            throw new IllegalArgumentException("Invalid username");
        }
        if (!validateEmail(email)) {
            throw new IllegalArgumentException("Invalid email");
        }
        if (!validateAge(age)) {
            throw new IllegalArgumentException("Invalid age");
        }

        User user = new User(users.size() + 1, username, email, age);
        save(user);
        return user;
    }

    // Formatting methods
    public String formatUserInfo(User user) {
        return String.format("User[id=%d, username=%s, email=%s, age=%d]",
            user.getId(), user.getUsername(), user.getEmail(), user.getAge());
    }

    public String formatUserList(List<User> userList) {
        StringBuilder sb = new StringBuilder();
        for (User user : userList) {
            sb.append(formatUserInfo(user)).append("\n");
        }
        return sb.toString();
    }

    // Inner class
    public static class User {
        private final int id;
        private final String username;
        private final String email;
        private final int age;

        public User(int id, String username, String email, int age) {
            this.id = id;
            this.username = username;
            this.email = email;
            this.age = age;
        }

        public int getId() { return id; }
        public String getUsername() { return username; }
        public String getEmail() { return email; }
        public int getAge() { return age; }
    }
}
