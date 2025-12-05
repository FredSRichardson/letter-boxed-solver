#!/usr/bin/env python3

# This version uses a scrabble dictionary

import argparse, re, string
import openfst_python as fst

EPSILON_TOK = '<epsilon>'

# Create Wordl[ey] FST from requested pattern:
def make_wdl_fst(cpat, requested):
    assert len(cpat) == 5, 'ERROR: make_wdl_fst() expects a list of 5 patterns'

    wdl_fst = fst.Fst()

    wt_one = fst.Weight.One(wdl_fst.weight_type())

    syms = fst.SymbolTable()

    syms.add_symbol(EPSILON_TOK)
    for c in string.ascii_uppercase:
        syms.add_symbol(c)
    
    assert syms.find(EPSILON_TOK) == 0, f'ERROR: "{EPSILON_TOK}" in' + \
        f' syms does not have index 0 ({syms.find(EPSILON_TOK)})'

    wdl_fst.set_input_symbols(syms)
    wdl_fst.set_output_symbols(syms)

    nodes = []
    for i in range(6):
        nodes.append(wdl_fst.add_state())
    wdl_fst.set_start(nodes[0])
    
    for i in range(1, 6):
        for c in cpat[i-1]:
            c_lbl = syms.find(c)
            wdl_fst.add_arc(nodes[i-1], fst.Arc(c_lbl, c_lbl, wt_one, nodes[i]))

    wdl_fst.set_final(nodes[-1])

    return wdl_fst


def make_lex_fst(lexicon):
    lex_fst = fst.Fst()

    isyms = fst.SymbolTable()
    osyms = fst.SymbolTable()

    isyms.add_symbol(EPSILON_TOK)
    for c in string.ascii_uppercase:
        isyms.add_symbol(c)

    osyms.add_symbol(EPSILON_TOK)
    for wrd in sorted(lexicon):
        osyms.add_symbol(wrd)

    assert isyms.find(EPSILON_TOK) == 0, f'ERROR: "{EPSILON_TOK}" in' + \
        f' isyms does not have index 0 ({isyms.find(EPSILON_TOK)})'
    assert osyms.find(EPSILON_TOK) == 0, f'ERROR: "{EPSILON_TOK}" in' + \
        f' osyms does not have index 0 ({osyms.find(EPSILON_TOK)})'

    lex_fst.set_input_symbols(isyms)
    lex_fst.set_output_symbols(osyms)

    s_start = lex_fst.add_state()
    s_end = lex_fst.add_state()

    lex_fst.set_start(s_start)

    wt_one = fst.Weight.One(lex_fst.weight_type())

    for wrd in sorted(lexicon):
        s_prev = s_start
        for ind, c in enumerate(wrd):
            s_new = lex_fst.add_state()
            ilbl = isyms.find(c)
            if ind == len(wrd) - 1:
                olbl = osyms.find(wrd)
                lex_fst.add_arc(s_prev, fst.Arc(ilbl, olbl, wt_one, s_end))
            else:
                olbl = 0
                lex_fst.add_arc(s_prev, fst.Arc(ilbl, olbl, wt_one, s_new))
            s_prev = s_new

    lex_fst.set_final(s_end)
    
    return lex_fst


pattern_hint = 'only ".", "C", "^ADF" are supported'

parser = argparse.ArgumentParser(description='Solve the NYT Letter Boxed puzzle using a word list')
parser.add_argument('-v', '--verbose', action='store_true',
                    help='increase output verbosity')

parser.add_argument('-ex', type=str,
                    help='Letters to exclude', 
                    default='')
parser.add_argument('-c1', type=str,
                    help='Pattern to search for first letter of 5 letter for - ' + pattern_hint, 
                    default='.')
parser.add_argument('-c2', type=str,
                    help='Pattern to search for first letter of 5 letter for - ' + pattern_hint, 
                    default='.')
parser.add_argument('-c3', type=str,
                    help='Pattern to search for first letter of 5 letter for - ' + pattern_hint, 
                    default='.')
parser.add_argument('-c4', type=str,
                    help='Pattern to search for first letter of 5 letter for - ' + pattern_hint, 
                    default='.')
parser.add_argument('-c5', type=str,
                    help='Pattern to search for first letter of 5 letter for - ' + pattern_hint, 
                    default='.')
parser.add_argument('-w','--word-list', type=str,
                    help='Word list to use',
                    required=True)
args = parser.parse_args()


c1 = args.c1.upper()
c2 = args.c2.upper()
c3 = args.c3.upper()
c4 = args.c4.upper()
c5 = args.c5.upper()

cpat = []

all_chars = set(string.ascii_uppercase)

req_chars = set()
for c in [ c1, c2, c3, c4, c5 ]:
    if c == '.':
        cpat.append(all_chars)
        continue
    # At this point, the pattern must be "[AB...]" or "[^AB...]":
    ret = re.match(r'^(\^?[A-Z]+)$', c)
    assert ret is not None, f'ERROR: unsupported pattern "{c}" - {pattern_hint}'
    pat_str = ret.group(1)
    # See if this is an exclusion pattern (i.e. "[^AB...]"):
    is_excl_pat = False
    if len(pat_str) > 0 and pat_str[0] == '^':
        is_excl_pat = True
        pat_str = pat_str[1:]
    else:
        # Only exclusion patterns can have more than one character:
        assert len(pat_str) == 1, f'ERROR: unsupported pattern "{c}" - {pattern_hint}'
    # All exclusion or inclusion chars are in the solution - they are required:
    for c in pat_str:
        req_chars.add(c)
    # Make sure pattern is still legit:
    assert len(pat_str) > 0, f'ERROR: unsupported pattern "{c}" - {pattern_hint}'
    pat_chars = set(pat_str)
    assert pat_chars <= all_chars, f'ERROR: Pattern contains non-letter characters in {c} - {pattern_hint}'
    if is_excl_pat:
        pat_chars = all_chars - pat_chars
    cpat.append(pat_chars)

wdl_fst = make_wdl_fst(cpat, req_chars)

# Set of letters that do not occur in the solution:
ex_chars = set(args.ex)

# Create the lexicon using the first word on each line, upper casing
# it and ensuring it's at least 3 letters:
lexicon = set()
with open(args.word_list) as ifp:
    for line in ifp:
        e = line.split()
        assert len(e) > 0, f'ERROR: each word list entry in "{args.word_list}"' + \
            f'must contain at least one word (not "{line.trim()}")'
        wrd = e[0].upper()
        # Word has to be 5 letters long:
        if len(wrd) != 5:
            continue
        # Words must contain required characters:
        if not set(wrd) >= req_chars:
            continue
        # Words cannot contain excluded characters
        if set(wrd) & ex_chars:
            continue
        lexicon.add(wrd)

print(f'Number of five letter words loaded from "{args.word_list}": {len(lexicon)}')

lex_fst = make_lex_fst(lexicon)

lex_fst = fst.determinize(lex_fst)

res_fst = fst.compose(wdl_fst, lex_fst)

nb_fst = fst.shortestpath(res_fst, nshortest=100).rmepsilon()

print('+++ Five letter words matching pattern: ')
for nd in nb_fst.states():
    for arc in nb_fst.arcs(nd):
        if arc.olabel != 0:
            wrd = nb_fst.output_symbols().find(arc.olabel)
            print(wrd)
