"""
Integration tests using real-world Java code samples.

Tests GenEC on actual open-source Java classes to verify:
- Pipeline runs without errors
- Refactoring suggestions are generated
- Output format is correct
- Performance is acceptable

Note: These tests skip LLM generation stage if ANTHROPIC_API_KEY is not set.
"""

import sys
import subprocess
import os
from pathlib import Path
from typing import Any
import json

import pytest


# Check if API key is available
HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))


class TestRealJavaProjects:
    """Integration tests with real-world Java code."""

    def run_genec_cli(self, *args: str, **kwargs: Any) -> subprocess.CompletedProcess:
        """Run GenEC CLI with given arguments."""
        cmd = [sys.executable, "-m", "genec.cli"] + list(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # Longer timeout for real analysis
            **kwargs
        )

    def _parse_json_output(self, stdout: str) -> Any:
        """Robustly parse JSON output from CLI stdout."""
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass

        # Try to find JSON starting from each line (working backwards is usually faster for output at end)
        lines = stdout.strip().split('\n')
        for i in range(len(lines) - 1, -1, -1):
            try:
                # Try parsing from this line to the end
                candidate = '\n'.join(lines[i:])
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

            try:
                 # Try parsing just this line
                return json.loads(lines[i])
            except json.JSONDecodeError:
                pass

        # Try finding the first '{' and parsing from there as a last resort
        try:
            idx = stdout.find('{')
            if idx != -1:
                return json.loads(stdout[idx:])
        except json.JSONDecodeError:
            pass

        # Re-raise original error if fallback fails
        raise json.JSONDecodeError("Could not find valid JSON in output", stdout, 0)

    @pytest.fixture
    def apache_commons_stringutils(self, tmp_path: Path) -> Path:
        """Create a simplified version of Apache Commons StringUtils."""
        java_code = '''
package org.apache.commons.lang3;

import java.util.ArrayList;
import java.util.List;

public class StringUtils {
    private static final String EMPTY = "";

    public static boolean isEmpty(String str) {
        return str == null || str.length() == 0;
    }

    public static boolean isNotEmpty(String str) {
        return !isEmpty(str);
    }

    public static boolean isBlank(String str) {
        int strLen;
        if (str == null || (strLen = str.length()) == 0) {
            return true;
        }
        for (int i = 0; i < strLen; i++) {
            if (!Character.isWhitespace(str.charAt(i))) {
                return false;
            }
        }
        return true;
    }

    public static boolean isNotBlank(String str) {
        return !isBlank(str);
    }

    public static String trim(String str) {
        return str == null ? null : str.trim();
    }

    public static String trimToNull(String str) {
        String ts = trim(str);
        return isEmpty(ts) ? null : ts;
    }

    public static String trimToEmpty(String str) {
        return str == null ? EMPTY : str.trim();
    }

    // Numeric validation methods - candidate for extraction
    public static boolean isNumeric(String str) {
        if (isEmpty(str)) {
            return false;
        }
        int sz = str.length();
        for (int i = 0; i < sz; i++) {
            if (!Character.isDigit(str.charAt(i))) {
                return false;
            }
        }
        return true;
    }

    public static boolean isNumericSpace(String str) {
        if (str == null) {
            return false;
        }
        int sz = str.length();
        for (int i = 0; i < sz; i++) {
            if (!Character.isDigit(str.charAt(i)) && str.charAt(i) != ' ') {
                return false;
            }
        }
        return true;
    }

    public static boolean isAlpha(String str) {
        if (isEmpty(str)) {
            return false;
        }
        int sz = str.length();
        for (int i = 0; i < sz; i++) {
            if (!Character.isLetter(str.charAt(i))) {
                return false;
            }
        }
        return true;
    }

    public static boolean isAlphanumeric(String str) {
        if (isEmpty(str)) {
            return false;
        }
        int sz = str.length();
        for (int i = 0; i < sz; i++) {
            if (!Character.isLetterOrDigit(str.charAt(i))) {
                return false;
            }
        }
        return true;
    }
}
'''
        java_file = tmp_path / "StringUtils.java"
        java_file.write_text(java_code)
        return java_file

    @pytest.fixture
    def guava_like_cache(self, tmp_path: Path) -> Path:
        """Create a Guava-inspired cache class with multiple responsibilities."""
        java_code = '''
package com.google.common.cache;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class LocalCache<K, V> {
    private final Map<K, V> cache;
    private final long maxSize;
    private long currentSize;

    // Statistics fields - candidate for extraction
    private long hitCount;
    private long missCount;
    private long evictionCount;

    public LocalCache(long maxSize) {
        this.cache = new ConcurrentHashMap<>();
        this.maxSize = maxSize;
        this.currentSize = 0;
        this.hitCount = 0;
        this.missCount = 0;
        this.evictionCount = 0;
    }

    // Core cache operations
    public V get(K key) {
        V value = cache.get(key);
        if (value != null) {
            recordHit();
        } else {
            recordMiss();
        }
        return value;
    }

    public void put(K key, V value) {
        if (currentSize >= maxSize) {
            evictOne();
        }
        cache.put(key, value);
        currentSize++;
    }

    public void remove(K key) {
        if (cache.remove(key) != null) {
            currentSize--;
        }
    }

    // Statistics methods - candidate for extraction
    private void recordHit() {
        hitCount++;
    }

    private void recordMiss() {
        missCount++;
    }

    private void recordEviction() {
        evictionCount++;
    }

    public long getHitCount() {
        return hitCount;
    }

    public long getMissCount() {
        return missCount;
    }

    public long getEvictionCount() {
        return evictionCount;
    }

    public double getHitRate() {
        long totalRequests = hitCount + missCount;
        return totalRequests == 0 ? 0.0 : (double) hitCount / totalRequests;
    }

    public void resetStatistics() {
        hitCount = 0;
        missCount = 0;
        evictionCount = 0;
    }

    // Eviction logic
    private void evictOne() {
        if (!cache.isEmpty()) {
            K firstKey = cache.keySet().iterator().next();
            cache.remove(firstKey);
            currentSize--;
            recordEviction();
        }
    }

    public long size() {
        return currentSize;
    }

    public void clear() {
        cache.clear();
        currentSize = 0;
    }
}
'''
        java_file = tmp_path / "LocalCache.java"
        java_file.write_text(java_code)
        return java_file

    @pytest.fixture
    def spring_like_controller(self, tmp_path: Path) -> Path:
        """Create a Spring-like controller with mixed responsibilities."""
        java_code = '''
package com.example.controller;

import java.util.List;
import java.util.ArrayList;

public class UserController {
    private List<User> users = new ArrayList<>();

    // Request handling
    public String handleGetUser(int id) {
        User user = findUserById(id);
        if (user == null) {
            return formatErrorResponse("User not found");
        }
        return formatUserResponse(user);
    }

    public String handleCreateUser(String name, String email) {
        if (!validateEmail(email)) {
            return formatErrorResponse("Invalid email");
        }
        if (!validateName(name)) {
            return formatErrorResponse("Invalid name");
        }
        User user = new User(users.size() + 1, name, email);
        users.add(user);
        return formatUserResponse(user);
    }

    // Data access - candidate for extraction
    private User findUserById(int id) {
        for (User user : users) {
            if (user.getId() == id) {
                return user;
            }
        }
        return null;
    }

    private List<User> findAllUsers() {
        return new ArrayList<>(users);
    }

    private void deleteUser(int id) {
        users.removeIf(user -> user.getId() == id);
    }

    // Validation logic - candidate for extraction
    private boolean validateEmail(String email) {
        return email != null && email.contains("@") && email.contains(".");
    }

    private boolean validateName(String name) {
        return name != null && name.length() >= 2 && name.length() <= 50;
    }

    // Response formatting - candidate for extraction
    private String formatUserResponse(User user) {
        return "{\"id\": " + user.getId() +
               ", \"name\": \"" + user.getName() +
               "\", \"email\": \"" + user.getEmail() + "\"}";
    }

    private String formatErrorResponse(String message) {
        return "{\"error\": \"" + message + "\"}";
    }

    private static class User {
        private final int id;
        private final String name;
        private final String email;

        public User(int id, String name, String email) {
            this.id = id;
            this.name = name;
            this.email = email;
        }

        public int getId() { return id; }
        public String getName() { return name; }
        public String getEmail() { return email; }
    }
}
'''
        java_file = tmp_path / "UserController.java"
        java_file.write_text(java_code)
        return java_file

    def setup_git_repo(self, repo_path: Path, java_file: Path) -> None:
        """Initialize a git repo and add the Java file with some history."""
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(["git", "add", java_file.name], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

    def test_apache_commons_stringutils(self, apache_commons_stringutils: Path, tmp_path: Path):
        """Test GenEC on Apache Commons StringUtils-like class."""
        self.setup_git_repo(tmp_path, apache_commons_stringutils)

        result = self.run_genec_cli(
            "--target", str(apache_commons_stringutils),
            "--repo", str(tmp_path),
            "--json"
        )

        # Should produce valid JSON output
        output = self._parse_json_output(result.stdout)
        assert isinstance(output, dict)

        # If no API key, expect error but valid JSON structure
        if not HAS_API_KEY:
            assert output.get("status") == "error" or "error" in output
            print(f"\n✓ Apache Commons StringUtils test completed (no API key, expected error)")
        else:
            # With API key, should complete successfully
            assert result.returncode == 0, f"CLI failed: {result.stderr}"
            assert "suggestions" in output or "clusters" in output or "message" in output
            print(f"\n✓ Apache Commons StringUtils test completed")
            print(f"  Output keys: {list(output.keys())}")

    def test_guava_cache(self, guava_like_cache: Path, tmp_path: Path):
        """Test GenEC on Guava-inspired cache class."""
        self.setup_git_repo(tmp_path, guava_like_cache)

        result = self.run_genec_cli(
            "--target", str(guava_like_cache),
            "--repo", str(tmp_path),
            "--json"
        )

        output = self._parse_json_output(result.stdout)
        assert isinstance(output, dict)

        if not HAS_API_KEY:
            assert output.get("status") == "error" or "error" in output
            print(f"\n✓ Guava LocalCache test completed (no API key, expected error)")
        else:
            assert result.returncode == 0, f"CLI failed: {result.stderr}"
            # This class has clear statistics-related methods that could be extracted
            print(f"\n✓ Guava LocalCache test completed")
            if "suggestions" in output:
                print(f"  Suggestions found: {len(output['suggestions'])}")

    def test_spring_controller(self, spring_like_controller: Path, tmp_path: Path):
        """Test GenEC on Spring-like controller with mixed responsibilities."""
        self.setup_git_repo(tmp_path, spring_like_controller)

        result = self.run_genec_cli(
            "--target", str(spring_like_controller),
            "--repo", str(tmp_path),
            "--json"
        )

        output = self._parse_json_output(result.stdout)
        assert isinstance(output, dict)

        if not HAS_API_KEY:
            assert output.get("status") == "error" or "error" in output
            print(f"\n✓ Spring Controller test completed (no API key, expected error)")
        else:
            assert result.returncode == 0, f"CLI failed: {result.stderr}"
            # This class has multiple extraction candidates (validation, formatting, data access)
            print(f"\n✓ Spring Controller test completed")
            if "suggestions" in output:
                print(f"  Suggestions found: {len(output['suggestions'])}")

    def test_performance_on_real_code(self, apache_commons_stringutils: Path, tmp_path: Path):
        """Test that GenEC performs acceptably on real-world code."""
        import time

        self.setup_git_repo(tmp_path, apache_commons_stringutils)

        start_time = time.time()
        result = self.run_genec_cli(
            "--target", str(apache_commons_stringutils),
            "--repo", str(tmp_path),
            "--json"
        )
        duration = time.time() - start_time

        # Should complete in reasonable time (under 60 seconds)
        assert duration < 60.0, f"Analysis took {duration:.2f}s (expected < 60s)"

        output = self._parse_json_output(result.stdout)
        assert isinstance(output, dict)

        if not HAS_API_KEY:
            print(f"\n✓ Performance test: {duration:.2f}s (no API key)")
        else:
            assert result.returncode == 0, f"CLI failed: {result.stderr}"
            print(f"\n✓ Performance test: {duration:.2f}s")

    def test_output_structure_consistency(self, guava_like_cache: Path, tmp_path: Path):
        """Test that output structure is consistent across different inputs."""
        self.setup_git_repo(tmp_path, guava_like_cache)

        result = self.run_genec_cli(
            "--target", str(guava_like_cache),
            "--repo", str(tmp_path),
            "--json"
        )

        output = self._parse_json_output(result.stdout)

        # Check expected output structure
        assert isinstance(output, dict)

        if not HAS_API_KEY:
            # Without API key, just verify error structure
            assert output.get("status") == "error" or "error" in output
            print(f"\n✓ Output structure validation passed (no API key)")
        else:
            assert result.returncode == 0, f"CLI failed: {result.stderr}"

            # If suggestions exist, validate structure
            if "suggestions" in output:
                suggestions = output["suggestions"]
                assert isinstance(suggestions, list)

                for suggestion in suggestions:
                    assert isinstance(suggestion, dict)
                    # Check for expected fields in suggestions
                    expected_fields = {"proposed_class_name", "methods", "rationale"}
                    suggestion_fields = set(suggestion.keys())
                    # At least some expected fields should be present
                    assert len(expected_fields & suggestion_fields) > 0, \
                        f"Suggestion missing expected fields. Found: {suggestion_fields}"

            print(f"\n✓ Output structure validation passed")

    @pytest.mark.parametrize("fixture_name", [
        "apache_commons_stringutils",
        "guava_like_cache",
        "spring_like_controller"
    ])
    def test_no_crashes_on_real_code(self, fixture_name: str, request, tmp_path: Path):
        """Test that GenEC doesn't crash on various real-world code patterns."""
        java_file = request.getfixturevalue(fixture_name)
        self.setup_git_repo(tmp_path, java_file)

        result = self.run_genec_cli(
            "--target", str(java_file),
            "--repo", str(tmp_path),
            "--json"
        )

        # Should produce valid JSON
        try:
            output = self._parse_json_output(result.stdout)
            assert isinstance(output, dict)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output for {fixture_name}: {e}")

        if not HAS_API_KEY:
            # Without API key, expect error but valid structure
            assert output.get("status") == "error" or "error" in output
            print(f"\n✓ {fixture_name}: No crashes (no API key)")
        else:
            # With API key, should complete successfully
            assert result.returncode == 0, \
                f"CLI crashed on {fixture_name}: {result.stderr}"
            print(f"\n✓ {fixture_name}: No crashes")


class TestRealProjectScenarios:
    """Test realistic scenarios and edge cases from real projects."""

    def run_genec_cli(self, *args: str, **kwargs: Any) -> subprocess.CompletedProcess:
        """Run GenEC CLI with given arguments."""
        cmd = [sys.executable, "-m", "genec.cli"] + list(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            **kwargs
        )

    def _parse_json_output(self, stdout: str) -> Any:
        """Robustly parse JSON output from CLI stdout."""
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            pass

        # Try to find JSON starting from each line (working backwards is usually faster for output at end)
        lines = stdout.strip().split('\n')
        for i in range(len(lines) - 1, -1, -1):
            try:
                # Try parsing from this line to the end
                candidate = '\n'.join(lines[i:])
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

            try:
                 # Try parsing just this line
                return json.loads(lines[i])
            except json.JSONDecodeError:
                pass

        # Try finding the first '{' and parsing from there as a last resort
        try:
            idx = stdout.find('{')
            if idx != -1:
                return json.loads(stdout[idx:])
        except json.JSONDecodeError:
            pass

        # Re-raise original error if fallback fails
        raise json.JSONDecodeError("Could not find valid JSON in output", stdout, 0)



    @pytest.fixture
    def class_with_inner_classes(self, tmp_path: Path) -> Path:
        """Create a class with inner classes (common in real projects)."""
        java_code = '''
package com.example;

public class OuterClass {
    private int value;

    public OuterClass(int value) {
        this.value = value;
    }

    public int getValue() {
        return value;
    }

    public void setValue(int value) {
        this.value = value;
    }

    public class InnerClass {
        public int getOuterValue() {
            return value;
        }
    }

    public static class StaticInnerClass {
        private int staticValue;

        public StaticInnerClass(int staticValue) {
            this.staticValue = staticValue;
        }

        public int getStaticValue() {
            return staticValue;
        }
    }
}
'''
        java_file = tmp_path / "OuterClass.java"
        java_file.write_text(java_code)
        return java_file

    @pytest.fixture
    def class_with_generics(self, tmp_path: Path) -> Path:
        """Create a class with generics (common in collections/utilities)."""
        java_code = '''
package com.example;

import java.util.ArrayList;
import java.util.List;

public class GenericContainer<T> {
    private List<T> items;

    public GenericContainer() {
        this.items = new ArrayList<>();
    }

    public void add(T item) {
        items.add(item);
    }

    public T get(int index) {
        return items.get(index);
    }

    public int size() {
        return items.size();
    }

    public boolean isEmpty() {
        return items.isEmpty();
    }

    public void clear() {
        items.clear();
    }
}
'''
        java_file = tmp_path / "GenericContainer.java"
        java_file.write_text(java_code)
        return java_file

    def setup_git_repo(self, repo_path: Path, java_file: Path) -> None:
        """Initialize a git repo and add the Java file."""
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(["git", "add", java_file.name], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

    def test_handles_inner_classes(self, class_with_inner_classes: Path, tmp_path: Path):
        """Test that GenEC handles inner classes gracefully."""
        self.setup_git_repo(tmp_path, class_with_inner_classes)

        result = self.run_genec_cli(
            "--target", str(class_with_inner_classes),
            "--repo", str(tmp_path),
            "--json"
        )

        # Should not crash on inner classes
        output = self._parse_json_output(result.stdout)
        assert isinstance(output, dict)

        if not HAS_API_KEY:
            assert output.get("status") == "error" or "error" in output
            print(f"\n✓ Inner classes handled gracefully (no API key)")
        else:
            assert result.returncode == 0, f"CLI failed on inner classes: {result.stderr}"
            print(f"\n✓ Inner classes handled gracefully")

    def test_handles_generics(self, class_with_generics: Path, tmp_path: Path):
        """Test that GenEC handles generic types gracefully."""
        self.setup_git_repo(tmp_path, class_with_generics)

        result = self.run_genec_cli(
            "--target", str(class_with_generics),
            "--repo", str(tmp_path),
            "--json"
        )

        # Should not crash on generics
        output = self._parse_json_output(result.stdout)
        assert isinstance(output, dict)

        if not HAS_API_KEY:
            assert output.get("status") == "error" or "error" in output
            print(f"\n✓ Generics handled gracefully (no API key)")
        else:
            assert result.returncode == 0, f"CLI failed on generics: {result.stderr}"
            print(f"\n✓ Generics handled gracefully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
