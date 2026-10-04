
shader_type spatial;
#ifdef GHOST
render_mode cull_back, blend_mix, depth_draw_never, shadows_disabled;
#else
render_mode cull_back;
#endif
uniform sampler2DArray alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray nrm : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray orm : filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 box_lo;
uniform vec3 box_hi;
uniform float glow_dim = -1.0;
uniform float glow_warm = -1.0;
uniform float glow_lamp = -1.0;
// share of windows lit (Weather: all at twilight, ~15 % in the city's afternoon)
global uniform float window_lit;
uniform float water_layer = -1.0;
uniform float plaster_layer = -1.0;
uniform float autumn_layer = -1.0;
uniform float lamps = 1.0;
global uniform float lamp_gain;
// rain in the city (Weather: Damp x CityHere). The region-weighted `wetness`
// is zero inside any region grade, so the kit has its own.
global uniform float city_wet;
uniform bool ghost = true;
global uniform vec3 player_pos;
// cloth in the wind (CityKit.Load): 1 hangs from sway_top, 2 streams from x = 0
uniform int sway_mode = 0;
uniform float sway_top = 0.0;
uniform vec3 cloth_layers = vec3(-1.0);
// a turning part (the windmill's sails): about +Z through spin_hub
uniform vec3 spin_hub = vec3(0.0);
uniform float spin_rate = 0.0;
// the waterfall asset: its water falls in its own space (CityKit.Load)
uniform float falls = 0.0;
varying vec3 lpos;
varying flat float layer;
// the instance's share of lit windows, x window_lit (its quarter's, CitySite)
varying flat float litk;
varying flat float occ;
varying flat float gone;
varying flat vec3 tint;
varying flat float seed;
#ifdef GHOST
// a ghosted occluder (CitySite.Ghosts): see-through and whole, in its own MeshInstance3D,
// so its tint and lit share come from an instance uniform, not INSTANCE_CUSTOM
instance uniform vec4 ghost_custom = vec4(1.0);
uniform float ghost_alpha = 0.3;
#endif
const float BAYER[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);

void vertex() {
    layer = floor(COLOR.r * 255.0 + 0.5);
#ifdef GHOST
    tint = ghost_custom.rgb;
#else
    tint = INSTANCE_CUSTOM.rgb;
#endif
    seed = fract(sin(dot(MODEL_MATRIX[3].xz, vec2(12.9898, 78.233))) * 43758.5453);
    lpos = VERTEX;
#ifdef GHOST
    litk = ghost_custom.a;
#else
    litk = INSTANCE_CUSTOM.a;
#endif
    if (sway_mode > 0 && any(lessThan(abs(vec3(layer) - cloth_layers), vec3(0.5)))) {
        float ph = dot(MODEL_MATRIX[3].xz, vec2(0.37, 0.61));
        float reach = sway_mode == 1 ? max(sway_top - VERTEX.y, 0.0) : abs(VERTEX.x);
        float w = sin(TIME * 2.3 + ph + reach * 1.7) * 0.6 + sin(TIME * 3.7 + ph * 1.3 + reach * 2.9) * 0.4;
        VERTEX.z += w * reach * (sway_mode == 1 ? 0.07 : 0.12);
        if (sway_mode == 2) VERTEX.y += w * reach * 0.03;
    }
    if (spin_rate != 0.0) {
        float a = TIME * spin_rate + dot(MODEL_MATRIX[3].xz, vec2(0.13, 0.07));
        float c = cos(a), s = sin(a);
        vec2 d = VERTEX.xy - spin_hub.xy;
        VERTEX.xy = spin_hub.xy + vec2(c * d.x - s * d.y, s * d.x + c * d.y);
        NORMAL.xy = vec2(c * NORMAL.x - s * NORMAL.y, s * NORMAL.x + c * NORMAL.y);
    }
    occ = 0.0;
    gone = 0.0;
    // only instances near the player can stand between it and the camera (26 m back)
    if (ghost && distance(MODEL_MATRIX[3].xyz, player_pos) < 60.0) {
        // into the instance's own space without a matrix inverse: its basis is a
        // rotation times a scale, so each axis is a dot product over its length squared
        vec3 c0 = MODEL_MATRIX[0].xyz, c1 = MODEL_MATRIX[1].xyz, c2 = MODEL_MATRIX[2].xyz;
        vec3 inv_s = 1.0 / vec3(dot(c0, c0), dot(c1, c1), dot(c2, c2));
        vec3 ca = CAMERA_POSITION_WORLD - MODEL_MATRIX[3].xyz;
        vec3 cb = player_pos + vec3(0.0, 0.9, 0.0) - MODEL_MATRIX[3].xyz;
        vec3 a = vec3(dot(ca, c0), dot(ca, c1), dot(ca, c2)) * inv_s;
        vec3 b = vec3(dot(cb, c0), dot(cb, c1), dot(cb, c2)) * inv_s;
        vec3 d = b - a;
        vec3 dd = mix(vec3(1e-5), d, step(vec3(1e-5), abs(d)));
        vec3 t0 = (box_lo - a) / dd;
        vec3 t1 = (box_hi - a) / dd;
        vec3 lo = min(t0, t1);
        vec3 hi = max(t0, t1);
        float enter = max(max(lo.x, lo.y), lo.z);
        float leave = min(min(hi.x, hi.y), hi.z);
        occ = (enter < leave && leave > 0.0 && enter < 0.97) ? 1.0 : 0.0;
        // against the lens: the camera inside or within 4 m of this box -- not drawn at all
        vec3 m = vec3(4.0) * sqrt(inv_s);
        if (all(greaterThan(a, box_lo - m)) && all(lessThan(a, box_hi + m))) gone = 1.0;
    }
}

void fragment() {
    vec3 uvw = vec3(UV, layer);
    vec3 c = texture(alb, uvw).rgb;
    ALBEDO = c * tint;
    // a limewash per house (2026-09-29, 'it is all grey'): cream, rose, ochre,
    // sage, peach -- pastel, so the street reads as lived-in, not poured
    if (abs(layer - plaster_layer) < 0.5)
        ALBEDO *= seed < 0.3 ? vec3(1.0) : seed < 0.48 ? vec3(1.05, 0.92, 0.90)
                : seed < 0.66 ? vec3(1.06, 0.97, 0.80) : seed < 0.82 ? vec3(0.94, 1.01, 0.88) : vec3(1.06, 0.93, 0.84);
    // autumn in the city's trees (2026-09-29; the user's newest references are
    // red and gold): each tree keeps its leaves' shading, recoloured
    // 2026-09-30 (the direction sheet: dark green trees against the orange dusk): 28 %
    if (abs(layer - autumn_layer) < 0.5 && seed > 0.72) {
        float l = dot(c, vec3(0.3, 0.59, 0.11)) / 0.12;
        vec3 leaf = seed < 0.82 ? vec3(0.55, 0.34, 0.06) : seed < 0.92 ? vec3(0.56, 0.19, 0.05) : vec3(0.42, 0.08, 0.05);
        ALBEDO = leaf * l * tint;
    }
    // a damp foot on buildings (not props): darker and greener up the first
    // half metre, so a house stands IN the street, not on it
    if (box_hi.y > 3.0) {
        float foot = 1.0 - smoothstep(-0.1, 0.55, lpos.y);
        ALBEDO *= mix(vec3(1.0), vec3(0.72, 0.77, 0.64), foot * 0.7);
    }
    NORMAL_MAP = texture(nrm, uvw).rgb;
    vec3 o = texture(orm, uvw).rgb;
    AO = o.r;
    AO_LIGHT_AFFECT = 0.5;
    ROUGHNESS = o.g;
    METALLIC = o.b;
    if (abs(layer - glow_dim) < 0.5 || abs(layer - glow_warm) < 0.5) {
        // one lit / unlit draw per window, from its place in the world
        vec3 w = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
        float pick = fract(sin(dot(floor(w * 0.7), vec3(12.9898, 78.233, 37.719))) * 43758.5453);
        float on = step(pick, window_lit * litk);
        // 0.8 / 2.6 -> 0.55 / 1.8 (2026-09-30): under the dusk grade's ACES the windows burned
        // white; the reference sheets' windows are orange
        float k = abs(layer - glow_dim) < 0.5 ? 0.55 : 1.8;
        EMISSION = c * k * lamps * lamp_gain * on;
        ALBEDO = mix(c * vec3(0.16, 0.17, 0.2), ALBEDO, on);
    }
    // lamp glass, lanterns, braziers, the forge: always burning
    // a dark house (CitySite.Dim, litk 0.12) has its lantern out
    if (abs(layer - glow_lamp) < 0.5) EMISSION = c * 2.6 * lamps * lamp_gain * step(0.2, litk);
    // how many screen pixels one rope / streak column spans, for the falls' fade
    float rope_px = fwidth(lpos.x * 9.0);
    float uv_px = fwidth(UV.x * 90.0);
    if (abs(layer - water_layer) < 0.5 && falls > 0.5) {
        // a waterfall (2026-09-24 night: 'falls read as flat panels'): ropes
        // of water of their own width and speed falling in the asset's own
        // height, white churn where it lands and a bright lip where it tips
        float h = clamp((lpos.y - box_lo.y) / max(box_hi.y - box_lo.y, 0.01), 0.0, 1.0);
        // thin ropes (9 per metre) with their own brightness and speed. 2026-09-30
        // (the gate views: 'blocky blue/white stripes'): each rope's value blends into
        // its neighbour's, the dash is a smooth wave (the sawtooth's reset was the hard
        // edge), and the pattern fades to its mean where a rope is under ~2 px
        float fx = lpos.x * 9.0;
        float c0 = floor(fx);
        float r = mix(fract(sin(c0 * 12.9898) * 43758.5453), fract(sin((c0 + 1.0) * 12.9898) * 43758.5453),
                      smoothstep(0.0, 1.0, fract(fx)));
        float wave = 0.5 + 0.5 * sin(6.2832 * (lpos.y * (0.7 + 0.5 * r) + TIME * (1.0 + 0.9 * r) + r * 7.0));
        float rope = pow(wave, 3.0) * (0.25 + 0.55 * r);
        rope = mix(0.12, rope, clamp(1.5 - rope_px, 0.0, 1.0));
        float churn = smoothstep(0.28, 0.0, h) * (0.6 + 0.4 * sin(TIME * 7.0 + lpos.x * 3.0 + lpos.z * 2.0));
        float lip = smoothstep(0.88, 0.98, h);
        vec3 deep = c * vec3(0.55, 0.7, 0.8);
        ALBEDO = mix(deep, vec3(0.94, 0.97, 1.0), clamp(rope * 0.8 + churn + lip * 0.7, 0.0, 1.0));
        ROUGHNESS = 0.2;
        EMISSION = ALBEDO * 0.3;
    }
    else if (abs(layer - water_layer) < 0.5) {
        // falling and running water: streaks sliding down the sheet, foam flecks
        // thin columns, each with its own speed and phase, dashes sliding down v
        float ux = UV.x * 90.0;
        float c0 = floor(ux);
        float r = mix(fract(sin(c0 * 12.9898) * 43758.5453), fract(sin((c0 + 1.0) * 12.9898) * 43758.5453),
                      smoothstep(0.0, 1.0, fract(ux)));
        float s = 0.5 + 0.5 * sin(6.2832 * (UV.y * 5.0 + TIME * (1.8 + 1.4 * r) + r * 7.0));
        float streak = pow(s, 3.0) * (0.35 + 0.65 * r);
        streak = mix(0.12, streak, clamp(1.5 - uv_px, 0.0, 1.0));
        ALBEDO = mix(c * 0.85, vec3(0.93, 0.97, 1.0), streak * 0.75);
        ROUGHNESS = 0.15;
        EMISSION = ALBEDO * 0.22;
    }
    // Wet by exposure (PENDING 'wet walls under eaves', done in the kit's one
    // shader): what faces the sky (roofs, sills, caps, paving on props) soaks
    // fully; walls only in the splash band near their foot, so the wall under
    // an eave stays dry. Darker and glossier.
    if (city_wet > 0.001) {
        vec3 wn = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
        float sky = smoothstep(0.35, 0.8, wn.y);
        float splash = 1.0 - smoothstep(0.3, 1.6, lpos.y - box_lo.y);
        float wet = city_wet * max(sky, 0.6 * splash);
        ALBEDO *= 1.0 - 0.35 * wet;
        ROUGHNESS = mix(ROUGHNESS, 0.22, wet);
    }
    if (gone > 0.5) discard;
    // ghosted whole: about a quarter drawn, dithered -- never a hole
    if (occ > 0.5) {
        int i = int(mod(FRAGCOORD.x, 4.0)) + 4 * int(mod(FRAGCOORD.y, 4.0));
        if ((BAYER[i] + 0.5) / 16.0 > 0.28) discard;
    }
#ifdef GHOST
    ALPHA = ghost_alpha;
#endif
}
