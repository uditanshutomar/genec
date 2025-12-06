package com.ecommerce.system;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.stream.Collectors;

/**
 * God Class: Order Management System
 *
 * This is a REALISTIC god class found in e-commerce systems that has grown over time.
 * It violates Single Responsibility Principle by handling multiple concerns:
 * 1. Order item management (add/remove items)
 * 2. Price calculation (tax, discounts, shipping)
 * 3. Payment processing
 * 4. Inventory management
 * 5. Shipping logistics
 * 6. Notification/Email sending
 * 7. Audit logging
 *
 * Expected Extractions (Ground Truth):
 * 1. OrderItemCollection - Manages order items (HIGH priority)
 * 2. PriceCalculator - Handles all pricing logic (HIGH priority)
 * 3. PaymentProcessor - Payment operations (MEDIUM priority)
 * 4. InventoryManager - Stock management (MEDIUM priority)
 * 5. ShippingCalculator - Shipping logic (MEDIUM priority)
 * 6. NotificationService - Email/notifications (LOW priority)
 *
 * Challenges for extraction tools:
 * - Shared dependencies (customer, items used by multiple groups)
 * - Method interdependencies (calculateTotal calls multiple price methods)
 * - Temporal coupling (payment + inventory must happen together)
 * - Ambiguous placement (audit logging - where does it belong?)
 */
public class OrderManagementSystem {

    // ========== DOMAIN OBJECTS ==========
    // These are shared across multiple responsibilities

    /**
	 * Extracted functionality - created by GenEC refactoring.
	 */
	private OrderFulfillmentEngine orderFulfillmentEngine = new OrderFulfillmentEngine();
	/**
	 * Extracted functionality - created by GenEC refactoring.
	 */
	private OrderPriceCalculator orderPriceCalculator = new OrderPriceCalculator();
	/**
	 * Extracted functionality - created by GenEC refactoring.
	 */
	private WarehouseInventoryTracker warehouseInventoryTracker = new WarehouseInventoryTracker();
	/**
	 * Extracted functionality - created by GenEC refactoring.
	 */
	private DiscountCalculator discountCalculator = new DiscountCalculator();
	/** Customer information */
    private String customerId;
    private String customerEmail;
    private String customerName;
    /** Order identification */
    private String orderId;
    private LocalDateTime orderDate;
    /** Order items - should be extracted */
    private List<OrderItem> items;
    private Map<String, Integer> itemQuantities;

    private BigDecimal totalAmount;

    /** Shipping data - should be extracted */
    private String shippingAddress;
    private String shippingCity;
    private String shippingZipCode;
    private String shippingCountry;
    private double packageWeight;
    private String shippingMethod; // "STANDARD", "EXPRESS", "OVERNIGHT"

    private List<String> reservedItems;

    /** Audit/logging data */
    private List<String> auditLog;
    private LocalDateTime lastModified;

    // ========== CONSTRUCTOR ==========

    public OrderManagementSystem(String customerId, String customerEmail, String customerName) {
        this.customerId = customerId;
        this.customerEmail = customerEmail;
        this.customerName = customerName;
        this.orderId = generateOrderId();
        this.orderDate = LocalDateTime.now();
        orderFulfillmentEngine.getOrderFulfillment().getOrderProcessor().setOrderStatus("PENDING");
        this.items = new ArrayList<>();
        this.itemQuantities = new HashMap<>();
        warehouseInventoryTracker.setWarehouseStock(new HashMap<>());
        this.reservedItems = new ArrayList<>();
        this.auditLog = new ArrayList<>();
        orderPriceCalculator.getPriceCalculator().setTaxRate(new BigDecimal("0.10"));
        discountCalculator.setDiscountPercentage(BigDecimal.ZERO);
        orderFulfillmentEngine.getOrderFulfillment().getOrderProcessor().setPaymentStatus("PENDING");
        this.lastModified = LocalDateTime.now();
    }

    // ========== GROUP 1: ORDER ITEM MANAGEMENT ==========
    // These methods should be extracted to OrderItemCollection

    /**
     * Add an item to the order.
     * Cohesion: HIGH - works with items collection
     */
    public void addItem(String productId, String productName, BigDecimal price, int quantity) {
        OrderItem item = new OrderItem(productId, productName, price, quantity);
        items.add(item);
        itemQuantities.put(productId, itemQuantities.getOrDefault(productId, 0) + quantity);
        logAudit("Added item: " + productName + " x" + quantity);
        recalculateSubtotal();
    }

    /**
     * Remove an item from the order.
     * Cohesion: HIGH - works with items collection
     */
    public void removeItem(String productId) {
        items.removeIf(item -> item.getProductId().equals(productId));
        itemQuantities.remove(productId);
        logAudit("Removed item: " + productId);
        recalculateSubtotal();
    }

    /**
     * Update item quantity.
     * Cohesion: HIGH - works with items collection
     */
    public void updateItemQuantity(String productId, int newQuantity) {
        for (OrderItem item : items) {
            if (item.getProductId().equals(productId)) {
                int oldQuantity = item.getQuantity();
                item.setQuantity(newQuantity);
                itemQuantities.put(productId, newQuantity);
                logAudit("Updated item " + productId + " quantity: " + oldQuantity + " -> " + newQuantity);
                recalculateSubtotal();
                return;
            }
        }
    }

    /**
     * Get item count.
     * Cohesion: HIGH - works with items collection
     */
    public int getItemCount() {
        return items.stream().mapToInt(OrderItem::getQuantity).sum();
    }

    /**
     * Get items by category.
     * Cohesion: HIGH - works with items collection
     */
    public List<OrderItem> getItemsByCategory(String category) {
        return items.stream()
                .filter(item -> item.getCategory().equals(category))
                .collect(Collectors.toList());
    }

    /**
     * Clear all items.
     * Cohesion: HIGH - works with items collection
     */
    public void clearItems() {
        items.clear();
        itemQuantities.clear();
        logAudit("Cleared all items");
        recalculateSubtotal();
    }

    // ========== GROUP 2: PRICE CALCULATION ==========
    // These methods should be extracted to PriceCalculator

    /**
     * Calculate subtotal from items.
     * Cohesion: HIGH - price calculation logic
     */
    private void recalculateSubtotal() {
        orderPriceCalculator.getPriceCalculator().setSubtotal(items.stream().map(item->item.getPrice().multiply(new BigDecimal(item.getQuantity()))).reduce(BigDecimal.ZERO,BigDecimal::add));
        calculateTotalAmount();
    }

    /**
     * Apply discount.
     * Cohesion: HIGH - price calculation logic
     */
    public void applyDiscount(BigDecimal percentage) {
		discountCalculator.applyDiscount(percentage);
	}

    /**
     * Apply customer tier discount.
     * Cohesion: HIGH - price calculation logic
     */
    public void applyTierDiscount() {
		discountCalculator.applyTierDiscount();
	}

    /**
     * Calculate discount amount.
     * Cohesion: HIGH - price calculation logic
     */
    public BigDecimal getDiscountAmount() {
		return orderPriceCalculator.getDiscountAmount();
	}

    /**
     * Calculate tax amount.
     * Cohesion: HIGH - price calculation logic
     */
    public BigDecimal getTaxAmount() {
		return orderPriceCalculator.getTaxAmount();
	}

    /**
     * Calculate total amount.
     * Cohesion: HIGH - price calculation logic
     * Challenge: Calls shipping calculation (cross-group dependency)
     */
    private void calculateTotalAmount() {
		discountCalculator.calculateTotalAmount();
	}

    /**
     * Get price breakdown.
     * Cohesion: HIGH - price calculation logic
     */
    public Map<String, BigDecimal> getPriceBreakdown() {
		return orderPriceCalculator.getPriceBreakdown();
	}

    // ========== GROUP 3: PAYMENT PROCESSING ==========
    // These methods should be extracted to PaymentProcessor

    /**
     * Process payment.
     * Cohesion: HIGH - payment logic
     * Challenge: Temporal coupling with inventory (both must succeed)
     */
    public boolean processPayment(String method, String cardNumber) {
		return orderFulfillmentEngine.processPayment(method, cardNumber);
	}

    /**
     * Simulate payment gateway.
     * Cohesion: HIGH - payment logic
     */
    private boolean simulatePaymentGateway(String method, String cardNumber, BigDecimal amount) {
		return orderFulfillmentEngine.simulatePaymentGateway(method, cardNumber, amount);
	}

    /**
     * Refund payment.
     * Cohesion: HIGH - payment logic
     */
    public boolean refundPayment() {
		return orderFulfillmentEngine.refundPayment();
	}

    /**
     * Validate payment details.
     * Cohesion: HIGH - payment logic
     */
    public boolean validatePaymentDetails(String method, String cardNumber) {
        if (method == null || cardNumber == null) return false;

        switch (method) {
            case "CREDIT_CARD":
                return cardNumber.length() >= 13 && cardNumber.length() <= 19;
            case "PAYPAL":
                return cardNumber.contains("@");
            case "BANK_TRANSFER":
                return cardNumber.length() >= 10;
            default:
                return false;
        }
    }

    // ========== GROUP 4: INVENTORY MANAGEMENT ==========
    // These methods should be extracted to InventoryManager

    /**
     * Check inventory availability.
     * Cohesion: HIGH - inventory logic
     */
    public boolean checkInventoryAvailability() {
        for (OrderItem item : items) {
            String productId = item.getProductId();
            int required = item.getQuantity();
            int available = warehouseInventoryTracker.getWarehouseStock().getOrDefault(productId, 0);

            if (available < required) {
                logAudit("Insufficient inventory for: " + productId);
                return false;
            }
        }
        return true;
    }

    /**
     * Reserve inventory for this order.
     * Cohesion: HIGH - inventory logic
     */
    private boolean reserveInventory() {
		return orderFulfillmentEngine.reserveInventory();
	}

    /**
     * Release reserved inventory.
     * Cohesion: HIGH - inventory logic
     */
    private void releaseInventory() {
		orderFulfillmentEngine.releaseInventory();
	}

    /**
     * Update warehouse stock.
     * Cohesion: HIGH - inventory logic
     */
    public void updateWarehouseStock(String productId, int quantity) {
		warehouseInventoryTracker.updateWarehouseStock(productId, quantity);
	}

    /**
     * Get low stock items.
     * Cohesion: HIGH - inventory logic
     */
    public List<String> getLowStockItems(int threshold) {
		return warehouseInventoryTracker.getLowStockItems(threshold);
	}

    // ========== GROUP 5: SHIPPING CALCULATION ==========
    // These methods should be extracted to ShippingCalculator

    /**
     * Set shipping address.
     * Cohesion: HIGH - shipping logic
     */
    public void setShippingAddress(String address, String city, String zipCode, String country) {
        this.shippingAddress = address;
        this.shippingCity = city;
        this.shippingZipCode = zipCode;
        this.shippingCountry = country;
        logAudit("Shipping address updated: " + city + ", " + country);
        calculateTotalAmount(); // Recalculate with shipping
    }

    /**
     * Calculate shipping cost based on weight and destination.
     * Cohesion: HIGH - shipping logic
     */
    private BigDecimal calculateShippingCost() {
		return orderPriceCalculator.calculateShippingCost();
	}

    /**
     * Get shipping method multiplier.
     * Cohesion: HIGH - shipping logic
     */
    private BigDecimal getShippingMethodMultiplier() {
		return orderPriceCalculator.getShippingMethodMultiplier();
	}

    /**
     * Estimate delivery date.
     * Cohesion: HIGH - shipping logic
     */
    public LocalDateTime estimateDeliveryDate() {
        if (shippingAddress == null) return null;

        int daysToDeliver;
        switch (shippingMethod != null ? shippingMethod : "STANDARD") {
            case "STANDARD":
                daysToDeliver = "US".equals(shippingCountry) ? 5 : 14;
                break;
            case "EXPRESS":
                daysToDeliver = "US".equals(shippingCountry) ? 2 : 7;
                break;
            case "OVERNIGHT":
                daysToDeliver = 1;
                break;
            default:
                daysToDeliver = 5;
        }

        return LocalDateTime.now().plus(daysToDeliver, ChronoUnit.DAYS);
    }

    /**
     * Set shipping method.
     * Cohesion: HIGH - shipping logic
     */
    public void setShippingMethod(String method) {
        this.shippingMethod = method;
        logAudit("Shipping method set: " + method);
        calculateTotalAmount(); // Recalculate shipping cost
    }

    // ========== GROUP 6: NOTIFICATION/EMAIL ==========
    // These methods should be extracted to NotificationService

    /**
     * Send order confirmation email.
     * Cohesion: HIGH - notification logic
     */
    private void sendOrderConfirmationEmail() {
        String subject = "Order Confirmation - " + orderId;
        String body = buildOrderConfirmationEmailBody();
        sendEmail(customerEmail, subject, body);
        logAudit("Order confirmation email sent to: " + customerEmail);
    }

    /**
     * Send payment confirmation email.
     * Cohesion: HIGH - notification logic
     */
    private void sendPaymentConfirmationEmail() {
		orderFulfillmentEngine.sendPaymentConfirmationEmail();
	}

    /**
     * Send shipping notification email.
     * Cohesion: HIGH - notification logic
     */
    public void sendShippingNotificationEmail(String trackingNumber) {
        String subject = "Order Shipped - " + orderId;
        String body = "Dear " + customerName + ",\n\n" +
                "Your order has been shipped!\n" +
                "Tracking number: " + trackingNumber + "\n" +
                "Estimated delivery: " + estimateDeliveryDate() + "\n\n" +
                "Thank you!";
        sendEmail(customerEmail, subject, body);
        logAudit("Shipping notification email sent: " + trackingNumber);
    }

    /**
     * Send refund notification email.
     * Cohesion: HIGH - notification logic
     */
    private void sendRefundNotificationEmail() {
		orderFulfillmentEngine.sendRefundNotificationEmail();
	}

    /**
     * Build order confirmation email body.
     * Cohesion: HIGH - notification logic
     */
    private String buildOrderConfirmationEmailBody() {
        StringBuilder body = new StringBuilder();
        body.append("Dear ").append(customerName).append(",\n\n");
        body.append("Thank you for your order!\n\n");
        body.append("Order ID: ").append(orderId).append("\n");
        body.append("Order Date: ").append(orderDate).append("\n\n");
        body.append("Items:\n");

        for (OrderItem item : items) {
            body.append("- ").append(item.getProductName())
                .append(" x").append(item.getQuantity())
                .append(" - $").append(item.getPrice())
                .append("\n");
        }

        body.append("\nTotal: $").append(totalAmount).append("\n\n");
        body.append("We will notify you when your order ships.\n\n");
        body.append("Best regards,\nThe Team");

        return body.toString();
    }

    /**
     * Send email (simulated).
     * Cohesion: HIGH - notification logic
     */
    private void sendEmail(String to, String subject, String body) {
		orderFulfillmentEngine.sendEmail(to, subject, body);
	}

    // ========== UTILITY/SHARED METHODS ==========
    // These are ambiguous - could belong to different classes or stay in base

    /**
     * Generate unique order ID.
     * Ambiguous: Could be utility, could stay in main class
     */
    private String generateOrderId() {
        return "ORD-" + System.currentTimeMillis() + "-" + (int)(Math.random() * 1000);
    }

    /**
     * Generate transaction ID.
     * Ambiguous: Could be in PaymentProcessor or utility
     */
    private String generateTransactionId() {
		return orderFulfillmentEngine.generateTransactionId();
	}

    /**
     * Log audit entry.
     * Ambiguous: Logging could be separate concern or infrastructure
     */
    private void logAudit(String message) {
		warehouseInventoryTracker.logAudit(message);
	}

    /**
     * Get audit log.
     */
    public List<String> getAuditLog() {
        return new ArrayList<>(auditLog);
    }

    // ========== GETTERS/SETTERS ==========
    // These should mostly stay in base class

    public String getOrderId() { return orderId; }
    public String getOrderStatus() {
		return orderFulfillmentEngine.getOrderStatus();
	}
    public BigDecimal getTotalAmount() {
		return orderPriceCalculator.getTotalAmount();
	}
    public String getCustomerId() { return customerId; }
    public String getCustomerEmail() { return customerEmail; }
    public LocalDateTime getOrderDate() { return orderDate; }
    public List<OrderItem> getItems() { return new ArrayList<>(items); }

    public void setCustomerTier(String tier) {
		discountCalculator.setCustomerTier(tier);
	}

    // ========== INNER CLASS ==========

    /**
     * Order item - represents a product in the order.
     */
    public static class OrderItem {
        private String productId;
        private String productName;
        private BigDecimal price;
        private int quantity;
        private String category;
        private double weight; // in kg

        public OrderItem(String productId, String productName, BigDecimal price, int quantity) {
            this.productId = productId;
            this.productName = productName;
            this.price = price;
            this.quantity = quantity;
            this.category = "General";
            this.weight = 1.0; // default weight
        }

        // Getters and setters
        public String getProductId() { return productId; }
        public String getProductName() { return productName; }
        public BigDecimal getPrice() { return price; }
        public int getQuantity() { return quantity; }
        public void setQuantity(int quantity) { this.quantity = quantity; }
        public String getCategory() { return category; }
        public void setCategory(String category) { this.category = category; }
        public double getWeight() { return weight; }
        public void setWeight(double weight) { this.weight = weight; }
    }
}
