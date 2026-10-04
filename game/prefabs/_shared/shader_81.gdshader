
shader_type spatial;
render_mode cull_disabled, shadows_disabled;
uniform float gust = 0.6;
const vec2 SIZE = vec2(12.4, 7.4);   // metres, yard x drop

void vertex() {
    float hold = sin(3.14159 * UV.x);
    float free = UV.y * UV.y;
    float breathe = (gust - 0.6) * 0.9 * hold * sin(1.5708 * UV.y);
    float flap = sin(TIME * 3.1 + UV.x * 9.0) * 0.05 * free + sin(TIME * 1.7 + UV.x * 4.0 + UV.y * 3.0) * 0.06 * UV.y * hold;
    VERTEX.x += breathe + flap;
}

float h(vec2 c) { return fract(sin(dot(c, vec2(127.1, 311.7))) * 43758.5453); }

void fragment() {
    vec2 px = floor(UV * SIZE * 52.0);
    vec2 m = px / 52.0;                       // metres across, metres down
    vec3 canvas = vec3(0.86, 0.82, 0.70);
    // sewn cloths, ~0.6 m wide, each a slightly different bolt
    float cloth = floor(m.x / 0.62);
    canvas *= 0.93 + 0.07 * h(vec2(cloth, 3.0));
    float seam = step(mod(m.x, 0.62), 0.04);
    // brails: dark lines every 1.8 m, with a fairlead ring every 0.9 m down
    float br = step(abs(mod(m.x + 0.9, 1.8) - 0.9), 0.035);
    float ring = br * step(mod(m.y, 0.9), 0.08);
    // weathering: yellowed and grimed toward the foot, a few streaks
    float streak = h(vec2(floor(m.x / 0.25), 7.0));
    canvas = mix(canvas, vec3(0.74, 0.64, 0.46), smoothstep(0.35, 1.0, UV.y) * 0.5 + step(0.82, streak) * 0.12 * UV.y);
    canvas *= 1.0 - 0.06 * h(px);             // cloth tooth
    vec3 col = mix(canvas, canvas * 0.82, seam);
    col = mix(col, vec3(0.28, 0.21, 0.14), max(br * 0.85, ring));
    // a darker band at the foot and at the head (the boltrope)
    col = mix(col, vec3(0.45, 0.36, 0.24), step(0.975, UV.y) + step(UV.y, 0.015));
    ALBEDO = col;
    ROUGHNESS = 0.95;
    SPECULAR = 0.0;
    // Light it mostly by the sail's overall facing (the ship's +X): the mesh
    // is flat-shaded, and the rows under the yard tilt hard into the belly,
    // so their lighting stepped into a hard tan band across the head.
    vec3 fwd = normalize((VIEW_MATRIX * MODEL_MATRIX * vec4(1.0, 0.0, 0.0, 0.0)).xyz);
    // One side for every face: Godot flips NORMAL on the face you see from
    // behind, and the rows under the yard are seen from the other side than
    // the rest -- they took the sky light from the far side and banded.
    NORMAL = normalize(mix(fwd, NORMAL * (FRONT_FACING ? 1.0 : -1.0), 0.25));
}

// Thin canvas passes light: lit the same from either face, and never fully
// dark on the side turned from the sun. With one-sided lambert the columns
// turned away took only the blue sky ambient and streaked (2026-09-23). No
// shadows received: the model's flat SHADOW_ sail cut a hard band across the
// billowed one.
void light() {
    float n = abs(dot(NORMAL, LIGHT));
    DIFFUSE_LIGHT += mix(n, 1.0, 0.4) * ATTENUATION * LIGHT_COLOR / PI;
}
