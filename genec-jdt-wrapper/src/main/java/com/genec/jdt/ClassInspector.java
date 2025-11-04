package com.genec.jdt;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.eclipse.jdt.core.dom.*;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * Command-line utility that inspects a Java class using Eclipse JDT and emits JSON metadata.
 */
public class ClassInspector {

    private static final Gson gson = new GsonBuilder().create();

    public static void main(String[] args) {
        String filePath = null;
        for (int i = 0; i < args.length; i++) {
            if ("--file".equals(args[i]) && i + 1 < args.length) {
                filePath = args[i + 1];
                break;
            }
        }

        if (filePath == null) {
            System.err.println("{\"error\":\"Missing --file argument\"}");
            System.exit(1);
        }

        try {
            String source = Files.readString(Paths.get(filePath), StandardCharsets.UTF_8);
            InspectorResult result = inspect(source);
            System.out.println(gson.toJson(result));
        } catch (IOException e) {
            System.err.println("{\"error\":\"Failed to read file: " + e.getMessage().replace("\"", "'") + "\"}");
            System.exit(1);
        } catch (Exception e) {
            System.err.println("{\"error\":\"Inspection failed: " + e.getMessage().replace("\"", "'") + "\"}");
            System.exit(1);
        }
    }

    private static InspectorResult inspect(String source) {
        ASTParser parser = ASTParser.newParser(AST.JLS17);
        parser.setSource(source.toCharArray());
        parser.setKind(ASTParser.K_COMPILATION_UNIT);
        parser.setResolveBindings(false);

        CompilationUnit compilationUnit = (CompilationUnit) parser.createAST(null);
        InspectorVisitor visitor = new InspectorVisitor(compilationUnit, source);
        compilationUnit.accept(visitor);
        return visitor.getResult();
    }

    private static class InspectorVisitor extends ASTVisitor {
        private final CompilationUnit compilationUnit;
        private final String source;
        private final InspectorResult result = new InspectorResult();
        private boolean classCaptured = false;

        InspectorVisitor(CompilationUnit compilationUnit, String source) {
            this.compilationUnit = compilationUnit;
            this.source = source;
            PackageDeclaration pkg = compilationUnit.getPackage();
            if (pkg != null) {
                result.packageName = pkg.getName().getFullyQualifiedName();
            } else {
                result.packageName = "";
            }
        }

        InspectorResult getResult() {
            return result;
        }

        @Override
        public boolean visit(TypeDeclaration node) {
            if (classCaptured) {
                return false;
            }
            classCaptured = true;

            result.className = node.getName().getIdentifier();
            result.modifiers = toStringList(node.modifiers());

            if (node.getSuperclassType() != null) {
                result.extendsName = node.getSuperclassType().toString();
            }

            List<String> interfaces = new ArrayList<>();
            for (Object iface : node.superInterfaceTypes()) {
                interfaces.add(iface.toString());
            }
            result.implementsList = interfaces;

            for (FieldDeclaration field : node.getFields()) {
                addField(field);
            }

            for (MethodDeclaration method : node.getMethods()) {
                addMethod(method);
            }

            return false; // No need to visit nested types
        }

        private void addField(FieldDeclaration field) {
            List<String> modifiers = toStringList(field.modifiers());
            String type = field.getType().toString();

            for (Object fragmentObj : field.fragments()) {
                VariableDeclarationFragment fragment = (VariableDeclarationFragment) fragmentObj;
                FieldDTO dto = new FieldDTO();
                dto.name = fragment.getName().getIdentifier();
                dto.type = type;
                dto.modifiers = modifiers;
                dto.line = compilationUnit.getLineNumber(fragment.getStartPosition());
                result.fields.add(dto);
            }
        }

        private void addMethod(MethodDeclaration method) {
            MethodDTO dto = new MethodDTO();
            dto.name = method.getName().getIdentifier();
            dto.modifiers = toStringList(method.modifiers());

            List<ParameterDTO> parameters = new ArrayList<>();
            for (Object paramObj : method.parameters()) {
                SingleVariableDeclaration param = (SingleVariableDeclaration) paramObj;
                ParameterDTO paramDTO = new ParameterDTO();
                paramDTO.name = param.getName().getIdentifier();
                paramDTO.type = param.getType().toString();
                if (param.isVarargs()) {
                    paramDTO.type = paramDTO.type + "...";
                }
                parameters.add(paramDTO);
            }
            dto.parameters = parameters;
            dto.signature = buildSignature(dto.name, parameters);

            if (method.isConstructor()) {
                dto.returnType = "";
            } else {
                Type returnType = method.getReturnType2();
                dto.returnType = returnType != null ? returnType.toString() : "void";
            }

            dto.startLine = compilationUnit.getLineNumber(method.getStartPosition());
            dto.endLine = compilationUnit.getLineNumber(method.getStartPosition() + method.getLength());
            dto.body = source.substring(method.getStartPosition(), method.getStartPosition() + method.getLength());
            dto.constructor = method.isConstructor();

            if (method.isConstructor()) {
                result.constructors.add(dto);
            } else {
                result.methods.add(dto);
            }
        }

        private List<String> toStringList(List<?> items) {
            List<String> out = new ArrayList<>();
            for (Object item : items) {
                out.add(item.toString());
            }
            return out;
        }

        private String buildSignature(String name, List<ParameterDTO> parameters) {
            StringBuilder sb = new StringBuilder(name).append("(");
            for (int i = 0; i < parameters.size(); i++) {
                if (i > 0) {
                    sb.append(",");
                }
                sb.append(parameters.get(i).type);
            }
            sb.append(")");
            return sb.toString();
        }
    }

    private static class InspectorResult {
        String className = "";
        String packageName = "";
        List<String> modifiers = new ArrayList<>();
        String extendsName = null;
        List<String> implementsList = new ArrayList<>();
        List<MethodDTO> methods = new ArrayList<>();
        List<MethodDTO> constructors = new ArrayList<>();
        List<FieldDTO> fields = new ArrayList<>();
    }

    private static class MethodDTO {
        String name;
        String signature;
        String returnType;
        List<String> modifiers;
        List<ParameterDTO> parameters;
        int startLine;
        int endLine;
        String body;
        boolean constructor;
    }

    private static class ParameterDTO {
        String name;
        String type;
    }

    private static class FieldDTO {
        String name;
        String type;
        List<String> modifiers;
        int line;
    }
}
