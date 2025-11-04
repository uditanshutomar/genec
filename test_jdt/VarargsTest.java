package com.example.test;

/**
 * Test class for verifying varargs signature matching
 */
public class VarargsTest {

    /**
	 * Extracted functionality - created by GenEC refactoring.
	 */
	private ArrayOperations arrayOperations = new ArrayOperations();
	public VarargsTest() {
        arrayOperations.setArray(new int[10]);
        arrayOperations.setSize(0);
    }

    // Method with varargs - should be extracted
    public void add(int index, int... values) {
		arrayOperations.add(index, values);
	}

    // Method with varargs - should be extracted
    public int[] insert(int position, int[] arr, int... elements) {
		return arrayOperations.insert(position, arr, elements);
	}

    // Regular method - should remain
    public int getSize() {
        return arrayOperations.getSize();
    }
}
