public class Test {
    /**
	 * Extracted functionality - created by GenEC refactoring.
	 */
	private ExtractedClass0 extractedClass0 = new ExtractedClass0();
	// Order Management
    private String orderId;
    private double orderTotal;
    private String shippingAddress;
    
    public void createUser(String u, String e, String p) {
		extractedClass0.createUser(u, e, p);
	}
    
    public void processOrder(String id, double total) {
        this.orderId = id;
        this.orderTotal = total;
        System.out.println("Processing order: " + id);
        validateAddress();
    }
    
    private void validateAddress() {
        if (shippingAddress == null) {
            System.out.println("Invalid address");
        }
    }
    
    public void sendEmail() {
		extractedClass0.sendEmail();
	}
}
