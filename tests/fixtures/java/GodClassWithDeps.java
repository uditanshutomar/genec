package com.test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

/**
 * God Class with collection management and statistics responsibilities.
 */
public class GodClassWithDeps {
    private List<String> items = new ArrayList<>();
    private List<Integer> scores = new ArrayList<>();
    private String label;

    // === Item Management ===
    public void addItem(String item) { items.add(item); }
    public void removeItem(String item) { items.remove(item); }
    public List<String> getItems() { return Collections.unmodifiableList(items); }
    public int getItemCount() { return items.size(); }
    public boolean hasItem(String item) { return items.contains(item); }
    public void clearItems() { items.clear(); }
    public List<String> searchItems(String prefix) {
        return items.stream().filter(i -> i.startsWith(prefix)).collect(Collectors.toList());
    }

    // === Score Statistics ===
    public void addScore(int score) { scores.add(score); }
    public double getAverageScore() {
        if (scores.isEmpty()) return 0.0;
        return scores.stream().mapToInt(Integer::intValue).average().orElse(0.0);
    }
    public int getMaxScore() {
        return scores.stream().mapToInt(Integer::intValue).max().orElse(0);
    }
    public int getMinScore() {
        return scores.stream().mapToInt(Integer::intValue).min().orElse(0);
    }
    public int getTotalScore() {
        return scores.stream().mapToInt(Integer::intValue).sum();
    }
    public List<Integer> getScoresAbove(int threshold) {
        return scores.stream().filter(s -> s > threshold).collect(Collectors.toList());
    }

    // === Label/Display ===
    public String getLabel() { return label; }
    public void setLabel(String l) { this.label = l; }
    public String getSummary() {
        return label + ": " + items.size() + " items, avg score: " + getAverageScore();
    }
}
