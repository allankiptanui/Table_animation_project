"""
Shader source code for the table project.
"""

VERTEX_SHADER_SRC = """
#version 330 core

in vec3 in_position;
uniform mat4 mvp;
uniform mat4 model;

out vec3 frag_position;

void main() {
    frag_position = (model * vec4(in_position, 1.0)).xyz;
    gl_Position = mvp * vec4(in_position, 1.0);
}
"""

FRAGMENT_SHADER_SRC = """
#version 330 core

in vec3 frag_position;
uniform vec3 color;
uniform vec3 light_position;

out vec4 out_color;

void main() {
    // Simple Lambertian shading with face normals
    vec3 normal = normalize(cross(dFdx(frag_position), dFdy(frag_position)));
    vec3 light_dir = normalize(light_position - frag_position);
    
    float diffuse = max(dot(normal, light_dir), 0.0);
    vec3 ambient = color * 0.2;
    vec3 diffuse_color = color * diffuse * 0.8;
    
    out_color = vec4(ambient + diffuse_color, 1.0);
}
"""

PICKING_SHADER_SRC = """
#version 330 core

uniform vec3 pick_color;
out vec4 out_color;

void main() {
    out_color = vec4(pick_color, 1.0);
}
"""