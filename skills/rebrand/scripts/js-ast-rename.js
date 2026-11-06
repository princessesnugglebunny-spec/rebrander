// JS/TS AST-aware identifier renamer using acorn (available system-wide).
// Usage: node js-ast-rename.js <brand.json> <file.js>
// Outputs renamed source to stdout. Exit 0 on success.
const fs = require('fs');
const acorn = require('/usr/share/nodejs/acorn');

const brandPath = process.argv[2];
const filePath = process.argv[3];

const brand = JSON.parse(fs.readFileSync(brandPath, 'utf8'));
const original = brand.original || {};
const target = brand.target || {};

// Build token pairs (same logic as brand_tokens.py, simplified).
function splitWords(tok) {
    return tok.split(/[\s_\-./]+/).flatMap(p => {
        const parts = p.match(/[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+/g);
        return parts || [p];
    }).filter(Boolean);
}

function style(words, form) {
    const low = words.map(w => w.toLowerCase());
    const cap = words.map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
    switch (form) {
        case 'lower': return low.join(' ');
        case 'upper': return words.map(w => w.toUpperCase()).join(' ');
        case 'snake': return low.join('_');
        case 'kebab': return low.join('-');
        case 'pascal': return cap.join('');
        case 'camel': return low[0] + cap.slice(1).join('');
        case 'concat': return low.join('');
        case 'upper_snake': return words.map(w => w.toUpperCase()).join('_');
        case 'upper_concat': return words.map(w => w.toUpperCase()).join('');
        default: return words.join(' ');
    }
}

const STYLES = ['lower','upper','snake','kebab','pascal','camel','concat','upper_snake','upper_concat'];
function variants(tok) {
    const words = splitWords(tok);
    const seen = new Set();
    const out = [];
    for (const f of STYLES) {
        const v = style(words, f);
        if (v && !seen.has(v)) { seen.add(v); out.push(v); }
    }
    if (tok && !seen.has(tok)) out.push(tok);
    return out;
}

// Build old->new pairs.
const pairs = [];
const keys = ['name', 'slug', 'org', 'domain', 'package', 'namespace'];
for (const k of keys) {
    if (original[k] && target[k] && original[k] !== target[k]) {
        const of = variants(original[k]);
        const nf = variants(target[k]);
        if (of.length === nf.length) {
            for (let i = 0; i < of.length; i++) {
                if (of[i] !== nf[i]) pairs.push([of[i], nf[i]]);
            }
        } else {
            pairs.push([original[k], target[k]]);
        }
    }
}
// Deduplicate.
const seen = new Set();
const deduped = [];
for (const [o, n] of pairs) {
    const key = o + '->' + n;
    if (!seen.has(key)) { seen.add(key); deduped.push([o, n]); }
}
// Sort by length descending.
deduped.sort((a, b) => b[0].length - a[0].length);

const pairMap = Object.fromEntries(deduped);

const source = fs.readFileSync(filePath, 'utf8');

// Parse with acorn.
let ast;
try {
    ast = acorn.parse(source, { ecmaVersion: 'latest', sourceType: 'module', locations: true });
} catch (e) {
    // Try script mode.
    try {
        ast = acorn.parse(source, { ecmaVersion: 'latest', sourceType: 'script', locations: true });
    } catch (e2) {
        process.stderr.write('Parse error: ' + e2.message + '\n');
        process.exit(2);
    }
}

// Collect identifier positions.
const idents = [];
function walk(node) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) { node.forEach(walk); return; }
    if (node.type === 'Identifier' && typeof node.start === 'number') {
        idents.push({ start: node.start, end: node.end, name: node.name });
    }
    for (const key of Object.keys(node)) {
        if (key === 'start' || key === 'end' || key === 'loc' || key === 'range') continue;
        walk(node[key]);
    }
}
walk(ast);

// Apply replacements from end to start to preserve positions.
let result = source;
// Sort by start descending.
idents.sort((a, b) => b.start - a.start);
let changes = 0;
for (const id of idents) {
    const replacement = pairMap[id.name];
    if (replacement) {
        // Check word boundary.
        const before = id.start > 0 ? source[id.start - 1] : '';
        const after = id.end < source.length ? source[id.end] : '';
        if (/[A-Za-z0-9_$]/.test(before) || /[A-Za-z0-9_$]/.test(after)) continue;
        result = result.slice(0, id.start) + replacement + result.slice(id.end);
        changes++;
    }
}

process.stdout.write(result);
process.stderr.write(JSON.stringify({ changes, file: filePath }) + '\n');
PY