
shader_type spatial;
render_mode specular_disabled;
global uniform vec3 player_pos;
global uniform float snow_depth;
global uniform float lamp_gain;
uniform vec3 albedo : source_color;
uniform vec2 ghost_size = vec2(2.0, 3.0);
const int BAYER[16] = { 0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5 };
varying flat float occ;
varying flat float gone;
varying flat float amt;
varying vec3 wpos;

float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(h(i), h(i + vec2(1.0, 0.0)), f.x), mix(h(i + vec2(0.0, 1.0)), h(i + vec2(1.0, 1.0)), f.x), f.y);
}

// (occ, gone), as the foliage shader does it for sprites: this object covers
// the player on screen and stands nearer the camera; or it is at the lens
vec2 ghost(mat4 model, mat4 view, mat4 proj) {
    vec2 r = vec2(0.0);
    if (proj[3][3] < 0.5) {
        float s = length(model[0].xyz);
        vec3 c = (view * model * vec4(0.0, ghost_size.y * 0.5, 0.0, 1.0)).xyz;
        vec3 pv = (view * vec4(player_pos + vec3(0.0, 0.9, 0.0), 1.0)).xyz;
        vec2 pp = pv.xy * (c.z / pv.z);
        vec2 gap = abs(pp - c.xy) - ghost_size * s * vec2(0.4, 0.45);
        r.x = smoothstep(1.0, -0.3, max(gap.x, gap.y)) * smoothstep(0.5, 2.0, c.z - pv.z);
        r.y = smoothstep(9.0, 5.0, -c.z);
    }
    return r;
}

bool hides(vec2 frag, float o, float gn) {
    if (o + gn <= 0.001) return false;
    int i = (int(frag.y) % 4) * 4 + int(frag.x) % 4;
    return (1.0 - 0.75 * o) * (1.0 - gn) < (float(BAYER[i]) + 0.5) / 16.0;
}

// pixel needles: a few darker and lighter texels, shaded bands like boughs
vec3 needle(vec3 base, vec2 uv) {
    vec2 q = floor(uv * 52.0);
    float n = h(q);
    vec3 c = base * (n < 0.18 ? 0.72 : (n > 0.86 ? 1.32 : 1.0));
    return c * (1.0 - 0.16 * step(0.68, fract(uv.y * 3.5 + h(vec2(floor(q.x / 3.0), 1.0)) * 0.35)));
}

const vec3 SNOW = vec3(0.86, 0.90, 0.96);

void vertex() {
    vec2 g = ghost(MODEL_MATRIX, VIEW_MATRIX, PROJECTION_MATRIX);
    occ = g.x;
    gone = g.y;
    amt = INSTANCE_CUSTOM.r * smoothstep(0.03, 0.75, snow_depth);
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
void fragment() {
    if (hides(FRAGCOORD.xy, occ, gone)) discard;
    vec2 q = floor(UV * 52.0);

    float s = h(vec2(floor(q.x / 2.0), 5.0));
    ALBEDO = albedo * (0.75 + 0.45 * s) * (h(q) < 0.08 ? 0.7 : 1.0);
    ROUGHNESS = 1.0;
}
