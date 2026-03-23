# GenEC Developer Study Protocol

## Study Design

**Type**: Within-subjects, blinded comparison study
**Goal**: Evaluate developer perception of GenEC refactoring suggestions vs. baseline

## Participants

- **Target**: 12-15 Java developers
- **Mix**: Industry developers (3-15 years experience) + PhD students (2-6 years)
- **Recruitment**: Lab group, SE course TAs, industry contacts
- **Criteria**: At least 1 year of Java development experience

## Materials Per Participant

Each participant reviews **5 GenEC suggestions** from different God Classes.
For naming quality comparison, each suggestion is shown alongside a baseline name.

### God Classes Used (from MLCQ benchmark):
1. IOUtils (Apache Commons IO) — 37 methods, utility class
2. SerializationUtils (Apache Commons Lang) — serialization
3. JobSchedulerService (Apache project) — scheduler service
4. FileUtils (Apache Commons IO) — file utilities
5. StringUtils (Apache Commons Lang) — string utilities

## Procedure

1. **Introduction** (5 min): Explain Extract Class refactoring concept, study goals
2. **Training** (5 min): Walk through one example refactoring (not from evaluation set)
3. **Evaluation** (30-40 min): Review 5 suggestions, fill survey for each
4. **Debrief** (5 min): Open discussion, qualitative feedback

## Survey Questions (per suggestion)

For each GenEC suggestion, participants see:
- The original God Class (key methods shown)
- The proposed extracted class (name, methods, fields)
- The rationale provided by GenEC
- Verification status (which tiers passed)

### Likert Scale Questions (1-5):
1. **Applicability**: "Would you apply this refactoring?" (1=Definitely not, 5=Definitely yes)
2. **Naming**: "Is the suggested class name appropriate?" (1=Poor, 5=Excellent)
3. **Cohesion**: "Are the method groupings cohesive?" (1=Arbitrary, 5=Highly cohesive)
4. **Quality**: "Does this improve code quality?" (1=No improvement, 5=Significant improvement)

### Naming Comparison (blinded):
- Show two names side by side (GenEC name vs. metric-based name like "IOUtils$Helper1")
- "Which name better describes the class's responsibility?" (A/B/Neither)
- "Rate the semantic clarity of each name" (1-5 for each)

### Open-Ended:
- "What aspects of the suggestion did you find most/least convincing?"
- "Would you modify the extraction before applying it? How?"

## Analysis Plan

### Quantitative:
- Median + IQR for Likert responses (ordinal data)
- Wilcoxon signed-rank test for naming comparison
- Overall acceptance rate: % of suggestions rated >= 4 on applicability

### Qualitative:
- Open coding of free-text responses
- Thematic analysis of modification suggestions
- Representative quotes for paper

## Ethical Considerations

- Participation is voluntary
- Responses are anonymized (P1, P2, ... P12)
- No personally identifiable information collected
- Study duration: ~45 minutes per participant
