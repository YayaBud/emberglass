
shader_type spatial;
render_mode diffuse_lambert_wrap, specular_disabled, cull_disabled, shadows_disabled;

uniform sampler2D tex : source_color, filter_nearest_mipmap;
uniform sampler2D tex_soft : source_color, filter_linear_mipmap;
uniform vec2 size_m;
uniform float foot_m;
global uniform vec3 player_pos;
global uniform float player_speed; // Foliage.Track, m/s
global uniform float wind;      // Weather: 1 dry, 3 in full rain, gusts on top
global uniform float snow_depth; // Snow.Depth
const int BAYER[16] = { 0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5 };

// occ 1 = this whole plant is in the way: its sprite box covers the player
// on screen and it stands nearer the camera -- drawn blurred and thin.
// gone 1 = it is against the lens -- not drawn at all: even a thin blurred
// layer of a sprite that close veils the whole frame (seen 2026-09-23).
varying flat float occ;
varying flat float gone;
// snow this plant carries now: its load (custom data) x the live depth
varying flat float snowy;

void vertex() {
    // A slow sway, strongest at the crown, still at the foot. Phased by the
    // plant's position so a row of trees never moves in step.
    vec3 org = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
    float up = clamp(1.0 - UV.y, 0.0, 1.0);
    VERTEX.x += sin(TIME * 1.1 * sqrt(wind) + org.x * 0.37 + org.z * 0.21) * 0.05 * wind * up * up;
    // brushed past: a small plant (bush, fern, reed -- not a tree) the player walks
    // through leans away from them and rustles, harder the faster they go
    float scale = length(MODEL_MATRIX[0].xyz);
    float small = 1.0 - smoothstep(1.8, 2.8, size_m.y * scale);
    if (small > 0.0) {
        vec2 rel = org.xz - player_pos.xz;
        float near = (1.0 - smoothstep(0.35, 1.3, length(rel))) * small
                   * (1.0 - smoothstep(1.0, 1.8, abs(org.y - player_pos.y)));
        vec2 side = normalize(MODEL_MATRIX[0].xz);
        float lean = dot(rel, side) >= 0.0 ? 1.0 : -1.0;
        float rustle = sin(TIME * 21.0 + org.x * 3.1 + org.z * 1.7) * clamp(player_speed / 6.0, 0.0, 1.0);
        VERTEX.x += (lean * 0.12 + rustle * 0.05) * near * up / max(scale, 0.01);
    }
    snowy = INSTANCE_CUSTOM.r * smoothstep(0.05, 0.45, snow_depth);

    // Perspective passes only: the sun's shadow pass is orthographic, so a
    // faded tree still casts its whole shadow.
    occ = 0.0;
    gone = 0.0;
    if (PROJECTION_MATRIX[3][3] < 0.5) {
        float s = length(MODEL_MATRIX[0].xyz);
        vec3 c = (VIEW_MATRIX * MODEL_MATRIX * vec4(0.0, size_m.y * 0.5 - foot_m, 0.0, 1.0)).xyz;
        vec3 pv = (VIEW_MATRIX * vec4(player_pos + vec3(0.0, 0.9, 0.0), 1.0)).xyz;
        vec2 pp = pv.xy * (c.z / pv.z);                    // the player carried to the plant's depth
        vec2 gap = abs(pp - c.xy) - size_m * s * vec2(0.4, 0.45);
        float over = smoothstep(1.0, -0.3, max(gap.x, gap.y));
        float nearer = smoothstep(0.5, 2.0, c.z - pv.z);
        occ = over * nearer;
        gone = smoothstep(9.0, 5.0, -c.z);
    }
}

void fragment() {
    vec4 c = texture(tex, UV);
    // Snow lies where there is open air a few texels above: the crown, and
    // every pine tier's shoulder, since each tier stands out past the one
    // above it. Deeper snow, a thicker rim; a dusting speckles the rest.
    // Shaded by the sprite's own painted light, so the lit side stays lit.
    if (snowy > 0.01 && c.a > 0.5) {
        vec2 px = 1.0 / vec2(textureSize(tex, 0));
        float reach = 2.0 + floor(snowy * 5.0);
        float air = 0.0;
        for (int k = 1; k <= 7; k++) {
            float y = UV.y - px.y * float(k);
            float a = y < 0.0 ? 0.0 : textureLod(tex, vec2(UV.x, y), 0.0).a;
            if (float(k) <= reach) air = max(air, step(a, 0.5));
        }
        // a sparse dusting in 2x2-texel clumps, not a per-texel speckle
        vec2 cl = floor(UV / px * 0.5);
        float dust = step(1.0 - snowy * 0.08, fract(sin(dot(cl, vec2(12.9898, 78.233))) * 43758.5453));
        float lum = dot(c.rgb, vec3(0.3, 0.59, 0.11));
        vec3 sn = mix(vec3(0.70, 0.75, 0.86), vec3(0.94, 0.96, 1.0), clamp(lum * 3.5, 0.0, 1.0));
        c.rgb = mix(c.rgb, sn, max(air, dust) * min(1.0, snowy * 1.6));
    }
    if (occ + gone > 0.001) {
        // In the way: blurred (a far mip, linearly filtered) and thinned to a
        // ghost by an ordered dither, so the whole frame stays readable.
        c = mix(c, texture(tex_soft, UV, 3.0 * occ), occ);
        int i = (int(FRAGCOORD.y) % 4) * 4 + int(FRAGCOORD.x) % 4;
        if (c.a * (1.0 - 0.75 * occ) * (1.0 - gone) < (float(BAYER[i]) + 0.5) / 16.0) discard;
        c.a = 1.0;
    }
    ALBEDO = c.rgb;
    ALPHA = c.a;
    ALPHA_SCISSOR_THRESHOLD = 0.5;
    ROUGHNESS = 1.0;
}
