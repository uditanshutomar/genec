# GenEC Tutorials

This guide provides step-by-step tutorials for using GenEC to refactor Java code.

## Table of Contents

1. [Getting Started: Your First Refactoring](#tutorial-1-getting-started)
2. [Refactoring a God Class](#tutorial-2-refactoring-a-god-class)
3. [Working with Configuration](#tutorial-3-working-with-configuration)
4. [Understanding Validation Results](#tutorial-4-understanding-validation-results)
5. [Advanced: Multi-file Projects](#tutorial-5-advanced-multi-file-projects)

---

## Tutorial 1: Getting Started

### Objective
Learn the basics of GenEC by refactoring a simple Java class.

### Prerequisites
- GenEC installed (`pip install -e .`)
- Anthropic API key set: `export ANTHROPIC_API_KEY='your-key'`
- A Java file in a Git repository

### Step 1: Create a Sample Java Class

Create a file `examples/tutorial1/Calculator.java`:

```java
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
```

### Step 2: Initialize Git Repository

```bash
cd examples/tutorial1
git init
git add Calculator.java
git commit -m "Initial commit"
```

### Step 3: Run GenEC

```bash
python -m genec.cli \
  --target examples/tutorial1/Calculator.java \
  --repo examples/tutorial1 \
  --json
```

### Step 4: Examine the Results

GenEC will output JSON with refactoring suggestions. Look for:

- **Clusters detected**: Groups of related methods
- **Suggestions**: Proposed new classes with extracted methods
- **Rationale**: Why these methods should be extracted together

### Expected Output

You should see suggestions to extract logging-related methods into a separate class like `OperationLogger`.

### Key Takeaways

- GenEC analyzes method dependencies automatically
- Git history helps identify co-changing methods
- Suggestions include rationale and complete code

---

## Tutorial 2: Refactoring a God Class

### Objective
Refactor a class with multiple responsibilities using GenEC's validation features.

### The Problem Class

Create `examples/tutorial2/UserManager.java`:

```java
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
```

### Step 1: Setup Repository

```bash
mkdir -p examples/tutorial2
cd examples/tutorial2
git init
git config user.email "test@example.com"
git config user.name "Test User"
git add UserManager.java
git commit -m "Initial UserManager"
```

### Step 2: Run GenEC with Verbose Output

```bash
python -m genec.cli \
  --target examples/tutorial2/UserManager.java \
  --repo examples/tutorial2 \
  --verbose \
  --json > results.json
```

### Step 3: Analyze Results

```bash
cat results.json | python -m json.tool
```

Look for multiple extraction suggestions:
- **UserValidator**: Validation methods
- **UserRepository**: Data access methods
- **UserFormatter**: Formatting methods

### Step 4: Understanding Validation

GenEC performs three-tier validation:

1. **Static Validation**: Checks for abstract methods, inner classes, private dependencies
2. **LLM Semantic Validation**: Intelligent analysis of borderline cases
3. **Pattern Transformation**: Suggests design patterns for blocked extractions

Check the output for:
- ✓ Valid suggestions in `data/outputs/UserManager/suggestion_*/`
- Pattern guidance in `data/outputs/UserManager/transformation_guidance/`

### Key Takeaways

- God classes often have multiple extraction opportunities
- GenEC identifies cohesive method groups automatically
- Validation prevents invalid extractions
- Pattern suggestions help enable blocked refactorings

---

## Tutorial 3: Working with Configuration

### Objective
Customize GenEC's behavior using the configuration file.

### Step 1: Understand Default Configuration

View the default config:

```bash
cat config/config.yaml
```

Key sections:
- `fusion`: Controls graph fusion (alpha parameter)
- `clustering`: Louvain algorithm parameters
- `verification`: Validation settings
- `llm`: Model selection and parameters

### Step 2: Create Custom Configuration

Create `examples/tutorial3/custom_config.yaml`:

```yaml
fusion:
  alpha: 0.7  # More weight on evolutionary coupling

clustering:
  min_cluster_size: 3  # Require at least 3 methods
  max_cluster_size: 15  # Limit cluster size

verification:
  enable_extraction_validation: true
  suggest_pattern_transformations: true
  enable_semantic: true

llm:
  model: claude-sonnet-4  # Use Sonnet 4
  max_tokens: 4000
  temperature: 0.2  # More deterministic

structural_transforms:
  enabled: true
  max_methods: 30  # Smaller threshold for structural plans
  max_fields: 15
```

### Step 3: Run with Custom Config

```bash
python -m genec.cli \
  --target examples/tutorial2/UserManager.java \
  --repo examples/tutorial2 \
  --config examples/tutorial3/custom_config.yaml \
  --json
```

### Step 4: Compare Results

With `alpha: 0.7`, GenEC weighs evolutionary coupling (Git history) more heavily than static dependencies. This is useful for:
- Mature codebases with rich Git history
- Finding methods that frequently change together
- Identifying implicit coupling not visible in code

### Step 5: Validate Configuration

GenEC uses Pydantic for type-safe configuration. Try an invalid value:

```yaml
fusion:
  alpha: 1.5  # Invalid: must be <= 1.0
```

```bash
python -m genec.cli \
  --target examples/tutorial2/UserManager.java \
  --repo examples/tutorial2 \
  --config examples/tutorial3/invalid_config.yaml
```

You'll get a clear error:
```
ValueError: Invalid configuration: fusion.alpha
  Input should be less than or equal to 1
```

### Key Takeaways

- Configuration is type-safe with Pydantic
- `alpha` controls static vs. evolutionary weight
- Clustering parameters affect suggestion granularity
- Invalid configs fail fast with clear messages

---

## Tutorial 4: Understanding Validation Results

### Objective
Learn to interpret GenEC's three-tier validation system.

### The Test Class

Create `examples/tutorial4/ServiceManager.java`:

```java
package com.example;

public abstract class ServiceManager {
    private DatabaseConnection db;
    private CacheManager cache;

    // Abstract method - will block extraction
    public abstract void initialize();

    // Methods using private field - extraction candidate
    public void saveToDatabase(String key, String value) {
        db.execute("INSERT INTO data VALUES (?, ?)", key, value);
        invalidateCache(key);
    }

    public String loadFromDatabase(String key) {
        String cached = getCachedValue(key);
        if (cached != null) {
            return cached;
        }
        String value = db.query("SELECT value FROM data WHERE key = ?", key);
        cacheValue(key, value);
        return value;
    }

    // Cache methods - extraction candidate
    private String getCachedValue(String key) {
        return cache.get(key);
    }

    private void cacheValue(String key, String value) {
        cache.put(key, value);
    }

    private void invalidateCache(String key) {
        cache.remove(key);
    }

    // Inner class - will complicate extraction
    public class CacheManager {
        public String get(String key) { return null; }
        public void put(String key, String value) {}
        public void remove(String key) {}
    }

    private static class DatabaseConnection {
        public void execute(String sql, Object... params) {}
        public String query(String sql, Object... params) { return null; }
    }
}
```

### Step 1: Run GenEC

```bash
cd examples/tutorial4
git init
git config user.email "test@example.com"
git config user.name "Test User"
git add ServiceManager.java
git commit -m "Initial commit"

python -m genec.cli \
  --target ServiceManager.java \
  --repo . \
  --verbose \
  --json > validation_results.json
```

### Step 2: Examine Validation Output

Check the logs for validation messages:

```
[Stage 5/6] Generating refactoring suggestions...
Validating cluster 0 (3 methods)...
❌ REJECTED: Contains abstract method 'initialize'
💡 Pattern suggestion: Consider implementing Template Method pattern

Validating cluster 1 (3 methods)...
✓ Static validation passed
🤖 LLM semantic validation: confidence 0.85
✓ APPROVED: Cache management methods
```

### Step 3: Review Pattern Suggestions

Check `data/outputs/ServiceManager/transformation_guidance/`:

```json
{
  "cluster_id": 0,
  "blocking_issues": ["abstract_methods"],
  "pattern_suggestions": [
    {
      "pattern": "Template Method",
      "rationale": "Abstract method 'initialize' suggests template pattern...",
      "implementation_steps": [...]
    }
  ]
}
```

### Step 4: Review Structural Plans

For large classes, check `data/outputs/structural_plans/ServiceManager/`:

```json
{
  "approach": "accessor_methods",
  "description": "Generate accessor methods for private field 'db'",
  "steps": [
    "Add protected getter for 'db'",
    "Update extracted class to call getter",
    "Verify compilation"
  ]
}
```

### Validation Tiers Explained

1. **Static Validation (~instant)**
   - Checks for abstract methods
   - Detects inner class usage
   - Verifies private dependencies are included
   - Auto-fixes missing transitive dependencies

2. **LLM Semantic Validation (~3-5s per cluster)**
   - Analyzes borderline cases
   - Confidence threshold: 0.7
   - Overrides conservative static rejections
   - Provides detailed reasoning

3. **Pattern Transformation (~3-5s per blocked cluster)**
   - Suggests design patterns
   - Provides implementation guidance
   - Helps enable blocked extractions

### Key Takeaways

- Three-tier validation prevents invalid refactorings
- Pattern suggestions help resolve blocking issues
- Structural plans guide complex transformations
- Confidence scores indicate extraction safety

---

## Tutorial 5: Advanced - Multi-file Projects

### Objective
Use GenEC on a realistic multi-class Java project.

### Project Structure

```
examples/tutorial5/
├── src/
│   └── com/
│       └── example/
│           ├── OrderProcessor.java
│           ├── PaymentService.java
│           └── NotificationService.java
└── pom.xml
```

### OrderProcessor.java

```java
package com.example;

import java.util.List;
import java.util.ArrayList;

public class OrderProcessor {
    private List<Order> orders = new ArrayList<>();
    private PaymentService paymentService = new PaymentService();
    private NotificationService notificationService = new NotificationService();

    // Order management
    public void processOrder(Order order) {
        validateOrder(order);
        calculateTotal(order);

        if (paymentService.charge(order.getTotal())) {
            orders.add(order);
            notificationService.sendOrderConfirmation(order);
        } else {
            notificationService.sendPaymentFailure(order);
        }
    }

    // Validation methods - extraction candidate
    private void validateOrder(Order order) {
        validateItems(order.getItems());
        validateAddress(order.getShippingAddress());
        validatePaymentMethod(order.getPaymentMethod());
    }

    private void validateItems(List<String> items) {
        if (items == null || items.isEmpty()) {
            throw new IllegalArgumentException("No items");
        }
    }

    private void validateAddress(String address) {
        if (address == null || address.trim().isEmpty()) {
            throw new IllegalArgumentException("Invalid address");
        }
    }

    private void validatePaymentMethod(String method) {
        if (!"CARD".equals(method) && !"PAYPAL".equals(method)) {
            throw new IllegalArgumentException("Invalid payment method");
        }
    }

    // Calculation methods - extraction candidate
    private void calculateTotal(Order order) {
        double subtotal = calculateSubtotal(order.getItems());
        double tax = calculateTax(subtotal);
        double shipping = calculateShipping(order.getShippingAddress());
        order.setTotal(subtotal + tax + shipping);
    }

    private double calculateSubtotal(List<String> items) {
        return items.size() * 10.0;  // Simplified
    }

    private double calculateTax(double subtotal) {
        return subtotal * 0.08;
    }

    private double calculateShipping(String address) {
        return address.contains("CA") ? 5.0 : 10.0;
    }

    public List<Order> getOrders() {
        return new ArrayList<>(orders);
    }

    public static class Order {
        private List<String> items;
        private String shippingAddress;
        private String paymentMethod;
        private double total;

        public Order(List<String> items, String address, String method) {
            this.items = items;
            this.shippingAddress = address;
            this.paymentMethod = method;
        }

        public List<String> getItems() { return items; }
        public String getShippingAddress() { return shippingAddress; }
        public String getPaymentMethod() { return paymentMethod; }
        public double getTotal() { return total; }
        public void setTotal(double total) { this.total = total; }
    }
}
```

### Step 1: Setup Project

```bash
cd examples/tutorial5
git init
git config user.email "test@example.com"
git config user.name "Test User"
git add src/
git commit -m "Initial order processing system"

# Add some history
# (Simulate co-changing validation methods)
sed -i '' 's/No items/Order must contain items/' src/com/example/OrderProcessor.java
git add src/
git commit -m "Improve validation messages"
```

### Step 2: Run GenEC

```bash
python -m genec.cli \
  --target src/com/example/OrderProcessor.java \
  --repo . \
  --max-suggestions 3 \
  --json > refactoring_suggestions.json
```

### Step 3: Review Suggestions

```bash
cat refactoring_suggestions.json | python -m json.tool | less
```

Expected suggestions:
1. **OrderValidator**: Extract validation methods
2. **OrderCalculator**: Extract calculation methods
3. **OrderNotifier**: Extract notification calls (if detected)

### Step 4: Apply a Refactoring

Use `--auto-apply` to automatically apply the best suggestion:

```bash
python -m genec.cli \
  --target src/com/example/OrderProcessor.java \
  --repo . \
  --auto-apply \
  --json
```

This will:
1. Generate the refactored code
2. Apply it using Eclipse JDT
3. Create a backup in `.genec_backups/`
4. Verify the refactoring compiles (if configured)

### Step 5: Review Applied Changes

```bash
# Check what changed
git diff src/com/example/OrderProcessor.java

# Check the new extracted class
ls src/com/example/

# Review the backup
ls .genec_backups/
```

### Step 6: Iterative Refactoring

Use `--apply-all` to iteratively apply all valid refactorings:

```bash
git add src/
git commit -m "Apply first refactoring"

python -m genec.cli \
  --target src/com/example/OrderProcessor.java \
  --repo . \
  --apply-all \
  --json
```

This will:
1. Apply the best refactoring
2. Re-analyze the modified class
3. Apply the next best refactoring
4. Repeat until no more valid refactorings found

### Key Takeaways

- GenEC works on real multi-file projects
- `--auto-apply` automatically applies best suggestion
- `--apply-all` iteratively applies all refactorings
- Backups are created automatically
- Git integration tracks co-changing methods
- Compilation can be verified (with Maven/Gradle)

---

## Next Steps

1. **Read the API Reference**: [API_REFERENCE.md](API_REFERENCE.md)
2. **Understand Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
3. **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
4. **Contribute**: See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)

## Common Tips

- **Start small**: Begin with simple classes before tackling god classes
- **Use verbose mode**: `--verbose` shows detailed pipeline stages
- **Review suggestions**: Always review before applying (`--auto-apply`)
- **Backup your code**: GenEC creates backups, but commit to Git first
- **Tune alpha**: Adjust `fusion.alpha` based on your Git history quality
- **Check validation**: Review `transformation_guidance/` for blocked extractions

## Getting Help

- **Issues**: https://github.com/YOUR_USERNAME/genec/issues
- **Discussions**: https://github.com/YOUR_USERNAME/genec/discussions
- **Documentation**: https://genec.readthedocs.io (coming soon)
