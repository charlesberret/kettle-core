/* Built-in color themes for setsweep. Each theme defines 16 ANSI terminal colors
   (indices 0–15) plus optional text/interface role overrides for dark and light. */
'use strict';

const ANSI_LABELS = [
  'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white',
  'bright black', 'bright red', 'bright green', 'bright yellow',
  'bright blue', 'bright magenta', 'bright cyan', 'bright white',
];

function ansiMap(arr) {
  const colors = {};
  arr.forEach((hex, i) => { colors[`--ansi-${i}`] = hex; });
  return colors;
}

const IFACE_DARK = {
  bg: '--ansi-0', fg: '--ansi-7', panel: '--ansi-8', panel2: '--ansi-0',
  line: '--ansi-8', acc: '--ansi-3', good: '--ansi-2', warn: '--ansi-1',
  selection: '--ansi-4', qtag: '--ansi-8', activebg: '--ansi-8',
  urghigh: '--ansi-1', urgmed: '--ansi-3', urglow: '--ansi-8',
};

const IFACE_LIGHT = {
  bg: '--ansi-15', fg: '--ansi-0', panel: '--ansi-7', panel2: '--ansi-15',
  line: '--ansi-8', acc: '--ansi-4', good: '--ansi-2', warn: '--ansi-1',
  selection: '--ansi-12', qtag: '--ansi-8', activebg: '--ansi-7',
  urghigh: '--ansi-1', urgmed: '--ansi-3', urglow: '--ansi-8',
};

const SLOTS_DARK = {
  header: '--ansi-3', ctxhead: '--ansi-7', ctxbody: '--ansi-7', ctxpath: '--ansi-4',
  cmthead: '--ansi-7', comment: '--ansi-4', wikilink: '--ansi-4',
  agent: '--ansi-8', user: '--ansi-3', glance: '--ansi-8',
};

const SLOTS_LIGHT = {
  header: '--ansi-4', ctxhead: '--ansi-0', ctxbody: '--ansi-0', ctxpath: '--ansi-4',
  cmthead: '--ansi-0', comment: '--ansi-4', wikilink: '--ansi-4',
  agent: '--ansi-8', user: '--ansi-4', glance: '--ansi-8',
};

function pack(colors16, slots, iface) {
  return { colors: ansiMap(colors16), slots, iface };
}

const BUILTIN_THEMES = {
  setsweep: {
    label: 'Setsweep',
    dark: pack(
      ['#16161e', '#d4756b', '#7dba6f', '#c8a24a', '#7d9fc8', '#9a76c2', '#389bb4', '#d8d8e0',
        '#32323f', '#e8928a', '#94c98a', '#d4b86a', '#9db4d8', '#b094d2', '#59b4cc', '#ececf2'],
      SLOTS_DARK, IFACE_DARK,
    ),
    light: pack(
      ['#f4f4f6', '#c0392b', '#2d7a3a', '#9a7200', '#2f5f9a', '#7a4a9a', '#18788a', '#1a1a22',
        '#d8d8de', '#d4756b', '#7dba6f', '#c8a24a', '#7d9fc8', '#9a76c2', '#389bb4', '#ffffff'],
      SLOTS_LIGHT, IFACE_LIGHT,
    ),
  },
  nord: {
    label: 'Nord',
    dark: pack(
      ['#2e3440', '#bf616a', '#a3be8c', '#ebcb8b', '#81a1c1', '#b48ead', '#88c0d0', '#eceff4',
        '#3b4252', '#d08770', '#b4d088', '#f0d890', '#5e81ac', '#c895c8', '#9dd0e0', '#e5e9f0'],
      SLOTS_DARK, IFACE_DARK,
    ),
    light: pack(
      ['#eceff4', '#bf616a', '#a3be8c', '#ebcb8b', '#5e81ac', '#b48ead', '#8fbcbb', '#2e3440',
        '#e5e9f0', '#d08770', '#a3be8c', '#ebcb8b', '#81a1c1', '#b48ead', '#88c0d0', '#ffffff'],
      SLOTS_LIGHT, IFACE_LIGHT,
    ),
  },
  tokyoNight: {
    label: 'Tokyo Night',
    dark: pack(
      ['#1a1b26', '#f7768e', '#9ece6a', '#e0af68', '#7aa2f7', '#bb9af7', '#7dcfff', '#c0caf5',
        '#414868', '#ff7a93', '#b9f27c', '#ffc777', '#89b4fa', '#cba6f7', '#a6e3ff', '#d5d6db'],
      SLOTS_DARK, IFACE_DARK,
    ),
    light: pack(
      ['#e1e2e7', '#f7768e', '#587539', '#8f6e00', '#34548a', '#7847aa', '#006a83', '#1a1b26',
        '#c4c8d4', '#f7768e', '#9ece6a', '#e0af68', '#7aa2f7', '#bb9af7', '#7dcfff', '#ffffff'],
      SLOTS_LIGHT, IFACE_LIGHT,
    ),
  },
  material: {
    label: 'Material',
    dark: pack(
      ['#121212', '#cf6679', '#03dac6', '#ffb74d', '#bb86fc', '#cf6679', '#03dac6', '#ffffff',
        '#1e1e1e', '#ffb4ab', '#66fff9', '#ffd180', '#d0bcff', '#ffb4ab', '#66fff9', '#e6e1e5'],
      SLOTS_DARK, IFACE_DARK,
    ),
    light: pack(
      ['#fafafa', '#b00020', '#018786', '#f57c00', '#6200ee', '#b00020', '#018786', '#1c1b1f',
        '#e6e1e5', '#cf6679', '#018786', '#f57c00', '#6200ee', '#7d5260', '#018786', '#ffffff'],
      SLOTS_LIGHT, IFACE_LIGHT,
    ),
  },
  solarized: {
    label: 'Solarized',
    dark: pack(
      ['#002b36', '#dc322f', '#859900', '#b58900', '#268bd2', '#d33682', '#2aa198', '#eee8d5',
        '#073642', '#cb4b16', '#586e75', '#657b83', '#839496', '#6c71c4', '#93a1a1', '#fdf6e3'],
      SLOTS_DARK, IFACE_DARK,
    ),
    light: pack(
      ['#fdf6e3', '#dc322f', '#859900', '#b58900', '#268bd2', '#d33682', '#2aa198', '#657b83',
        '#eee8d5', '#cb4b16', '#93a1a1', '#839496', '#657b83', '#6c71c4', '#586e75', '#002b36'],
      SLOTS_LIGHT, IFACE_LIGHT,
    ),
  },
  gruvbox: {
    label: 'Gruvbox',
    dark: pack(
      ['#282828', '#cc241d', '#98971a', '#d79921', '#458588', '#b16286', '#689d6a', '#ebdbb2',
        '#3c3836', '#fb4934', '#b8bb26', '#fabd2f', '#83a598', '#d3869b', '#8ec07c', '#fbf1c7'],
      SLOTS_DARK, IFACE_DARK,
    ),
    light: pack(
      ['#fbf1c7', '#cc241d', '#79740e', '#b57614', '#076678', '#8f3f71', '#427b58', '#3c3836',
        '#ebdbb2', '#9d0006', '#79740e', '#b57614', '#076678', '#8f3f71', '#427b58', '#ffffff'],
      SLOTS_LIGHT, IFACE_LIGHT,
    ),
  },
  oneDark: {
    label: 'One Dark',
    dark: pack(
      ['#282c34', '#e06c75', '#98c379', '#e5c07b', '#61afef', '#c678dd', '#56b6c2', '#abb2bf',
        '#3e4451', '#be5046', '#98c379', '#d19a66', '#61afef', '#c678dd', '#56b6c2', '#ffffff'],
      SLOTS_DARK, IFACE_DARK,
    ),
    light: pack(
      ['#fafafa', '#e45649', '#50a14f', '#c18401', '#4078f2', '#a626a4', '#0184bc', '#383a42',
        '#e5e5e6', '#e06c75', '#98c379', '#e5c07b', '#61afef', '#c678dd', '#56b6c2', '#ffffff'],
      SLOTS_LIGHT, IFACE_LIGHT,
    ),
  },
  classic: {
    label: 'Classic ANSI',
    dark: pack(
      ['#000000', '#cd0000', '#00cd00', '#cdcd00', '#0000ee', '#cd00cd', '#00cdcd', '#e5e5e5',
        '#7f7f7f', '#ff0000', '#00ff00', '#ffff00', '#5c5cff', '#ff00ff', '#00ffff', '#ffffff'],
      SLOTS_DARK, IFACE_DARK,
    ),
    light: pack(
      ['#ffffff', '#cd0000', '#00cd00', '#cdcd00', '#0000ee', '#cd00cd', '#00cdcd', '#000000',
        '#e5e5e5', '#ff0000', '#00ff00', '#ffff00', '#5c5cff', '#ff00ff', '#00ffff', '#000000'],
      SLOTS_LIGHT, IFACE_LIGHT,
    ),
  },
};

/** Map legacy --c-* keys from older settings to --ansi-* */
const LEGACY_PALETTE_KEYS = {
  '--c-black': '--ansi-0', '--c-red': '--ansi-1', '--c-green': '--ansi-2', '--c-yellow': '--ansi-3',
  '--c-blue': '--ansi-4', '--c-purple': '--ansi-5', '--c-indigo': '--ansi-5', '--c-teal': '--ansi-6',
  '--c-white': '--ansi-7', '--c-gray1': '--ansi-8', '--c-gray2': '--ansi-8', '--c-gray3': '--ansi-8',
  '--c-gray4': '--ansi-8', '--c-gray5': '--ansi-8', '--c-gray6': '--ansi-15', '--c-orange': '--ansi-1',
};

const XTERM_DEFAULTS = BUILTIN_THEMES.classic.dark.colors;
