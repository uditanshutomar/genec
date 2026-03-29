# Candidate Benchmark Classes for GenEC Evaluation

## Summary
27 candidate God Classes across 8 new projects, ranked by suitability for Extract Class refactoring evaluation.

## Selection Criteria
- Large classes (1000+ LOC) with many methods
- Maven or Gradle build system (GenEC uses `mvn compile` for verification)
- Good test coverage (behavioral equivalence verification)
- Rich Git history (evolutionary coupling analysis)
- Well-known open-source projects (reviewer credibility)
- Diverse domains

---

## TIER 1: Highest Priority (Classic Refactoring Benchmarks)

These projects are used as standard evaluation subjects in Extract Class literature (Bavota et al., JDeodorant, HECS).

### Project 1: Google Closure Compiler
- **Domain:** JavaScript compiler/optimizer
- **Clone URL:** `https://github.com/google/closure-compiler.git`
- **Build:** Maven (`mvn compile`)
- **Tests:** Extensive JUnit test suite
- **Git History:** 10,000+ commits, very active
- **Defects4J:** Yes (176 bugs in Defects4J benchmark)
- **Why:** Used in Defects4J, massive well-tested classes, rich history

| # | Class | File Path | ~LOC | Notes |
|---|-------|-----------|------|-------|
| 1 | NodeUtil | `src/com/google/javascript/jscomp/NodeUtil.java` | ~5,600 | AST utility, pure God Class |
| 2 | Compiler | `src/com/google/javascript/jscomp/Compiler.java` | ~4,700 | Main compiler orchestrator |
| 3 | TypedScopeCreator | `src/com/google/javascript/jscomp/TypedScopeCreator.java` | ~4,600 | Type system scope creation |
| 4 | TypeCheck | `src/com/google/javascript/jscomp/TypeCheck.java` | ~3,900 | Type checking visitor |
| 5 | JsDocInfoParser | `src/com/google/javascript/jscomp/parsing/JsDocInfoParser.java` | ~2,800 | JSDoc parser |
| 6 | CommandLineRunner | `src/com/google/javascript/jscomp/CommandLineRunner.java` | ~2,500 | CLI argument processing |
| 7 | CodeGenerator | `src/com/google/javascript/jscomp/CodeGenerator.java` | ~2,200 | AST to source code |

### Project 2: Apache Lucene
- **Domain:** Full-text search engine
- **Clone URL:** `https://github.com/apache/lucene.git`
- **Build:** Gradle (`gradle build`)
- **Tests:** Extensive test suite with randomized testing
- **Git History:** 15,000+ commits
- **Why:** Premier search library, massive classes, excellent tests

| # | Class | File Path | ~LOC | Notes |
|---|-------|-----------|------|-------|
| 8 | IndexWriter | `lucene/core/src/java/org/apache/lucene/index/IndexWriter.java` | ~7,300 | Classic God Class, index management |

### Project 3: Apache Xerces2-J
- **Domain:** XML parser
- **Clone URL:** `https://github.com/apache/xerces2-j.git`
- **Build:** Ant (with Maven POM available) -- **CAVEAT: Ant primary, not Maven**
- **Tests:** JUnit tests available
- **Git History:** Moderate
- **Why:** Classic refactoring benchmark (Bavota et al., GanttProject+Xerces evaluation)

| # | Class | File Path | ~LOC | Notes |
|---|-------|-----------|------|-------|
| 9 | AbstractDOMParser | `src/org/apache/xerces/parsers/AbstractDOMParser.java` | ~3,000 | DOM parsing God Class |
| 10 | XMLDTDValidator | `src/org/apache/xerces/impl/dtd/XMLDTDValidator.java` | ~2,400 | DTD validation |
| 11 | XMLDocumentFragmentScannerImpl | `src/org/apache/xerces/impl/XMLDocumentFragmentScannerImpl.java` | ~1,900 | XML scanning |
| 12 | XMLDocumentScannerImpl | `src/org/apache/xerces/impl/XMLDocumentScannerImpl.java` | ~1,600 | Document scanning |

---

## TIER 2: High Priority (Enterprise Frameworks)

### Project 4: Spring Framework
- **Domain:** Enterprise Java framework
- **Clone URL:** `https://github.com/spring-projects/spring-framework.git`
- **Build:** Gradle (`./gradlew build`)
- **Tests:** Extensive test suite
- **Git History:** 25,000+ commits, extremely active
- **Why:** Most widely-used Java framework, deep class hierarchies

| # | Class | File Path | ~LOC | Notes |
|---|-------|-----------|------|-------|
| 13 | DefaultListableBeanFactory | `spring-beans/src/main/java/org/springframework/beans/factory/support/DefaultListableBeanFactory.java` | ~3,000 | IoC container core, classic God Class |
| 14 | AbstractAutowireCapableBeanFactory | `spring-beans/src/main/java/org/springframework/beans/factory/support/AbstractAutowireCapableBeanFactory.java` | ~2,300 | Bean creation/wiring |
| 15 | AbstractBeanFactory | `spring-beans/src/main/java/org/springframework/beans/factory/support/AbstractBeanFactory.java` | ~2,300 | BeanFactory base |
| 16 | AbstractApplicationContext | `spring-context/src/main/java/org/springframework/context/support/AbstractApplicationContext.java` | ~1,800 | Application context lifecycle |
| 17 | DispatcherServlet | `spring-webmvc/src/main/java/org/springframework/web/servlet/DispatcherServlet.java` | ~1,700 | MVC front controller |

### Project 5: Hibernate ORM
- **Domain:** Object-Relational Mapping
- **Clone URL:** `https://github.com/hibernate/hibernate-orm.git`
- **Build:** Gradle (`./gradlew build`)
- **Tests:** Extensive integration tests
- **Git History:** 15,000+ commits
- **Why:** Standard Java ORM, massive session management classes

| # | Class | File Path | ~LOC | Notes |
|---|-------|-----------|------|-------|
| 18 | SemanticQueryBuilder | `hibernate-core/src/main/java/org/hibernate/query/hql/internal/SemanticQueryBuilder.java` | ~6,500 | HQL query parsing |
| 19 | SessionImpl | `hibernate-core/src/main/java/org/hibernate/internal/SessionImpl.java` | ~2,600 | Core Session implementation |

### Project 6: Apache Tomcat
- **Domain:** Java Servlet container / Web server
- **Clone URL:** `https://github.com/apache/tomcat.git`
- **Build:** Ant (`ant deploy`) -- **CAVEAT: Ant primary**
- **Tests:** JUnit tests
- **Git History:** 20,000+ commits
- **Why:** Most-used Java web server, HTTP request handling God Classes

| # | Class | File Path | ~LOC | Notes |
|---|-------|-----------|------|-------|
| 20 | StandardContext | `java/org/apache/catalina/core/StandardContext.java` | ~5,200 | Web application context management |
| 21 | Request | `java/org/apache/catalina/connector/Request.java` | ~2,800 | HTTP request wrapper |
| 22 | Http11Processor | `java/org/apache/coyote/http11/Http11Processor.java` | ~1,600 | HTTP/1.1 protocol processing |

### Project 7: Elasticsearch
- **Domain:** Distributed search and analytics engine
- **Clone URL:** `https://github.com/elastic/elasticsearch.git`
- **Build:** Gradle (`./gradlew assemble`)
- **Tests:** Extensive randomized testing framework
- **Git History:** 80,000+ commits, extremely active
- **Why:** Major distributed systems project, complex cluster management classes

| # | Class | File Path | ~LOC | Notes |
|---|-------|-----------|------|-------|
| 23 | IndexShard | `server/src/main/java/org/elasticsearch/index/shard/IndexShard.java` | ~6,700 | Shard lifecycle management |
| 24 | MetadataCreateIndexService | `server/src/main/java/org/elasticsearch/cluster/metadata/MetadataCreateIndexService.java` | ~3,100 | Index creation |
| 25 | IndicesService | `server/src/main/java/org/elasticsearch/indices/IndicesService.java` | ~2,800 | Indices lifecycle |
| 26 | MasterService | `server/src/main/java/org/elasticsearch/cluster/service/MasterService.java` | ~2,600 | Cluster master coordination |
| 27 | Metadata | `server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java` | ~2,500 | Cluster metadata |

---

## TIER 3: Secondary Options (if more diversity needed)

### Project 8: Apache POI
- **Domain:** Microsoft Office document processing
- **Clone URL:** `https://github.com/apache/poi.git`
- **Build:** Gradle (`./gradlew build`)
- **Tests:** Good test coverage
- **Git History:** 5,000+ commits

| # | Class | File Path | ~LOC | Notes |
|---|-------|-----------|------|-------|
| 28 | XSSFSheet | `poi-ooxml/src/main/java/org/apache/poi/xssf/usermodel/XSSFSheet.java` | ~5,800 | Excel sheet manipulation |
| 29 | XSSFWorkbook | `poi-ooxml/src/main/java/org/apache/poi/xssf/usermodel/XSSFWorkbook.java` | ~2,800 | Excel workbook management |

### Other Investigated But Lower Priority

| Project | Class | ~LOC | Issue |
|---------|-------|------|-------|
| ArgoUML | FigNodeModelElement | ~2,700 | Ant build only, old codebase, hard to compile |
| ArgoUML | ProjectBrowser | ~2,100 | Ant build only |
| JHotDraw 7 | SVGInputFormat | ~4,100 | Maven available but dated; small test suite |
| JHotDraw 7 | DefaultDrawingView | ~1,600 | Same issues as above |
| GanttProject | GanttProject | ~800 | Too small for God Class evaluation |
| Apache Ant | Project | ~2,700 | Ant build (obviously), no Maven |
| Apache Ant | IntrospectionHelper | ~2,200 | Ant build only |
| Joda-Time | DateTimeFormatterBuilder | ~2,900 | Good but only 1 viable class |
| Google Guava | Maps | ~4,800 | Utility class with mostly static methods, less interesting for Extract Class |

---

## Recommended Final Benchmark (40-50 classes total)

### Existing (23 classes, 6 projects):
- Apache Commons IO (3), Lang (5), Collections (3), Text (3), Math (4)
- JFreeChart (5)

### New additions (27 classes, 7 projects):
- Google Closure Compiler (7 classes) -- Defects4J project, Maven, excellent tests
- Spring Framework (5 classes) -- Gradle, premier enterprise framework
- Elasticsearch (5 classes) -- Gradle, excellent randomized tests
- Hibernate ORM (2 classes) -- Gradle, standard ORM benchmark
- Apache Tomcat (3 classes) -- Ant build (may need wrapper)
- Apache Lucene (1 class) -- Gradle, legendary search library
- Apache Xerces2-J (4 classes) -- Ant build (classic benchmark)

**TOTAL: 50 classes across 13 projects**

### Build System Compatibility Notes:
- **Maven native:** Closure Compiler, (existing Apache Commons projects)
- **Gradle native:** Spring, Hibernate, Elasticsearch, Lucene, POI
- **Ant only:** Tomcat, Xerces2-J (may need mvn wrapper or skip verification)

For GenEC's `mvn compile` verification step, the Gradle projects can use `./gradlew compileJava` instead. The Ant projects (Tomcat, Xerces) would require either a Maven wrapper or verification-skip mode.
