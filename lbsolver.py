#!/usr/bin/env python3

# This version uses a scrabble dictionary

# TODO: use single word parsed FST to create viable single word lexicon
# Then use that lexicon to create trigram.
# There's no need to make N-gram - we're already doing that as part of the lexicon creation...

import argparse, re, math
import openfst_python as fst

EPSILON_TOK = '<epsilon>'

def find_paths(current_state, current_data, fst_obj, paths):
    no_out_arcs = True

    for arc in fst_obj.arcs(current_state):
        no_out_arcs = False
        # Get input and output symbols (using symbol tables if available)
        input_symbol = fst_obj.input_symbols().find(arc.ilabel) if fst_obj.input_symbols() else str(arc.ilabel)
        output_symbol = fst_obj.output_symbols().find(arc.olabel) if fst_obj.output_symbols() else str(arc.olabel)
        
        # Recursively call for the next state
        find_paths(arc.nextstate, current_data + [ (input_symbol, output_symbol, float(arc.weight)) ], fst_obj, paths)

    if no_out_arcs:
        paths.append(current_data)


def split_lb_side(astr):
    astr = astr.upper()
    ret = re.match(r'^\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*$', astr)
    if ret is None: 
        return None
    return ret.groups()

def make_lex_fst(lb_set, lb_wrds, word_pair=False):
    lex_fst = fst.Fst()

    isyms = fst.SymbolTable()
    osyms = fst.SymbolTable()

    isyms.add_symbol(EPSILON_TOK)
    for c in lb_set:
        isyms.add_symbol(c)

    osyms.add_symbol(EPSILON_TOK)
    for wrd, _ in lb_wrds:
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
    lex_fst.set_final(s_end)

    wt_one = fst.Weight.One(lex_fst.weight_type())

    for wrd1, wrd1_set in lb_wrds:
        l1 = wrd1[-1]
        # The score is the number of unique lettesr in the word
        # plus a small amount that favors shorter words
        n_uniq = len(wrd1_set)
        scr = -n_uniq + -(500 - len(wrd1)) / 10000.0
        # at least 3 unique letters covered by first word:
        if n_uniq < 3: continue
        s_prev = s_start
        s_wrd1_end = None
        for ind, c in enumerate(wrd1):
            ilbl = isyms.find(c)
            if ind == 0:
                s_new = lex_fst.add_state()
                olbl = osyms.find(wrd1)
                lex_fst.add_arc(s_prev, fst.Arc(ilbl, olbl, scr, s_new))
            elif ind == len(wrd1) - 1:
                s_new = s_end
                olbl = 0
                lex_fst.add_arc(s_prev, fst.Arc(ilbl, olbl, wt_one, s_new))
                # save second-to-last state for next word:
                s_wrd1_end = s_prev
            else:
                s_new = lex_fst.add_state()
                olbl = 0
                lex_fst.add_arc(s_prev, fst.Arc(ilbl, olbl, wt_one, s_new))
            s_prev = s_new
        if not word_pair:
            continue
        for wrd2, wrd2_set in lb_wrds:
            if wrd2[0] != l1:
                continue
            n_uniq = len(wrd2_set - wrd1_set)
            scr = -n_uniq + -(500-len(wrd2)) / 10000.0
            # at least 3 more unique letters covered by second word:
            if n_uniq < 3: continue
            # Second to last state of previous word - we're sharing the same letter:
            s_prev = s_wrd1_end
            # skip the first letter (note - this code would break on 2 letter words..):
            for ind, c in enumerate(wrd2):
                ilbl = isyms.find(c)
                if ind == 0:
                    s_new = lex_fst.add_state()
                    olbl = osyms.find(wrd2)
                    lex_fst.add_arc(s_prev, fst.Arc(ilbl, olbl, scr, s_new))
                elif ind == len(wrd2) - 1:
                    s_new = s_end
                    olbl = 0
                    lex_fst.add_arc(s_prev, fst.Arc(ilbl, olbl, wt_one, s_new))
                else:
                    s_new = lex_fst.add_state()
                    olbl = 0
                    lex_fst.add_arc(s_prev, fst.Arc(ilbl, olbl, wt_one, s_new))
                s_prev = s_new
    
    return lex_fst

def make_lb_fst(lb_sides, lex_fst):
    assert len(lb_sides) == 4, 'ERROR: expect a list of 4 letter tuples for "lb_sides"'

    lb_fst = fst.Fst()

    wt_one = fst.Weight.One(lb_fst.weight_type())

    s_start = lb_fst.add_state()
    s_end = lb_fst.add_state()

    isyms = lex_fst.input_symbols()

    lb_fst.set_input_symbols(isyms)
    lb_fst.set_output_symbols(isyms)

    lb_fst.set_start(s_start)

    # Create a node for each letter on each side stored as:
    # [ [ nl1, nl2, nl3 ], ..., [nb1, nb2, nb3 ] ]
    lb_nodes = []
    for iside in range(4):
        snodes = []
        for ic in lb_sides[iside]:
            snodes.append(lb_fst.add_state())
        lb_nodes.append(snodes)

    # for each side:
    for iside in range(4):
        inodes = []
        # for each letter in that side:
        for iind, ic in enumerate(lb_sides[iside]):
            # Get the node:
            inode = lb_nodes[iside][iind]
            ilbl = isyms.find(ic)
            # Create an arc from the start node:
            lb_fst.add_arc(s_start, fst.Arc(0, ilbl, wt_one, inode))
            # Create an arc to the end node:
            lb_fst.add_arc(inode, fst.Arc(0, 0, wt_one, s_end))
            # Now for all the other sides:
            for jside in range(4):
                if iside == jside:
                    continue
                # For each letter on those sides:
                for jind, jc in enumerate(lb_sides[jside]):
                    # Get the other node
                    jnode = lb_nodes[jside][jind]
                    jlbl = isyms.find(jc)
                    # Create an arc from the letter on side-i 
                    # to the letter on side-j
                    lb_fst.add_arc(inode, fst.Arc(0, jlbl, wt_one, jnode))

    # lb_fst.add_arc(s_end, fst.Arc(0, 0, wt_one, s_start))

    lb_fst.set_final(s_end)
    
    return lb_fst
    

parser = argparse.ArgumentParser(description='Solve the NYT Letter Boxed puzzle using a word list')
parser.add_argument('-v', '--verbose', action='store_true',
                    help='increase output verbosity')
parser.add_argument('--lex-fst', type=str, help='Save the lexicon FST in GraphViz format')
parser.add_argument('--lb-fst', type=str, help='Save the Letter Boxed FST in GraphViz format')
parser.add_argument('-l','--left', type=str,
                    help='Left edge of Letter Boxed puzzle', 
                    required=True)
parser.add_argument('-r','--right', type=str,
                    help='Right edge of Letter Boxed puzzle', 
                    required=True)
parser.add_argument('-t','--top', type=str,
                    help='Top edge of Letter Boxed puzzle', 
                    required=True)
parser.add_argument('-b','--bottom', type=str,
                    help='Bottom edge of Letter Boxed puzzle', 
                    required=True)
parser.add_argument('-w','--word-list', type=str,
                    help='Word list to use',
                    required=True)
args = parser.parse_args()

DEBUG = False
# DEBUG = True

if DEBUG:
    args.verbose = True
    args.left = 'CHO'
    args.top = 'PFN'
    args.right = 'AIT'
    args.bottom = 'RDL'

lb_t = split_lb_side(args.top)
lb_l = split_lb_side(args.left)
lb_r = split_lb_side(args.right)
lb_b = split_lb_side(args.bottom)

assert lb_t is not None, f'ERROR: --top should contain exactly 3 letters (not "{args.top}")'
assert lb_l is not None, f'ERROR: --left should contain exactly 3 letters (not "{args.left}")'
assert lb_r is not None, f'ERROR: --right should contain exactly 3 letters (not "{args.right}")'
assert lb_b is not None, f'ERROR: --bottom should contain exactly 3 letters (not "{args.bottom}")'

# Create the lexicon using the first word on each line, upper casing
# it and ensuring it's at least 3 letters:
lexicon = set()
with open(args.word_list) as ifp:
    for line in ifp:
        e = line.split()
        assert len(e) > 0, f'ERROR: each word list entry in "{args.word_list}"' + \
            f'must contain at least one word (not "{line.trim()}")'
        wrd = e[0].upper()
        if len(wrd) < 3:
            continue
        lexicon.add(wrd)


if args.verbose:
    print(f'Number of words loaded from "{args.word_list}": {len(lexicon)}')
            
# Get the set of all Letter Boxed letters:
lb_set = set(lb_t + lb_l + lb_r + lb_b)

# Get words that only contain letters in the Letter Boxed set:

if DEBUG:
    lexicon = set([ 'HANDCLAP', 'HANDCRAFT', 'PORTFOLIO', 'TROPICAL' ])


lb_wrds = []
for wrd in sorted(lexicon):
    if len(wrd) < 3:
        continue
    wrd_set = set(wrd)
    if wrd_set - lb_set:
        continue
    lb_wrds.append( (wrd, wrd_set) )

lex_fst = make_lex_fst(lb_set, lb_wrds, word_pair=False)
lex_fst.arcsort(sort_type="ilabel")
lb_fst = make_lb_fst( [ lb_t, lb_l, lb_r, lb_b ], lex_fst)
lblg_fst = fst.compose(lb_fst, lex_fst)
lblg_fst = lblg_fst.rmepsilon()
nb_fst = fst.shortestpath(lblg_fst, nshortest=100).rmepsilon()
paths = []
find_paths(nb_fst.start(), [], nb_fst, paths)
lexicon = set()
for p in paths:
    for c in p:
        lexicon.add(c[1])
lb_wrds = []
for wrd in sorted(lexicon):
    if len(wrd) < 3:
        continue
    wrd_set = set(wrd)
    if wrd_set - lb_set:
        continue
    lb_wrds.append( (wrd, wrd_set) )

if args.verbose:
    print('Creating lexicon FST.')
lex_fst = make_lex_fst(lb_set, lb_wrds, word_pair=True)
if args.verbose:
    print('Lexicon FST created.')

if False:
    # These seem to be fragile
    print('Applying determinize to lexicon FST.')
    lex_fst = fst.determinize(lex_fst)

    print('Applying rmepsilon to lexicon FST.')
    lex_fst = lex_fst.rmepsilon()
    print('Applying minimize to lexicon FST.')
    lex_fst = lex_fst.minimize()

lex_fst.arcsort(sort_type="ilabel")

if DEBUG:
    print(lex_fst)
    print('')

if args.verbose:
    print('Creating letter boxed FST.')
lb_fst = make_lb_fst( [ lb_t, lb_l, lb_r, lb_b ], lex_fst)
if args.verbose:
    print('Letter boxed FST created.')

if args.verbose:
    print('Composing Letter Boxed FST and Lexicon FST.')
lblg_fst = fst.compose(lb_fst, lex_fst)
lblg_fst = lblg_fst.rmepsilon()
if args.verbose:
    print('Composition complete')
if DEBUG:
    print(lblg_fst)
    print('')

nb_fst = fst.shortestpath(lblg_fst, nshortest=100).rmepsilon()

paths = []
find_paths(nb_fst.start(), [], nb_fst, paths)

for p in paths:
    scr = sum([ c[2] for c in p ])
    wrds = ' '.join([ c[1] for c in p ])
    n_match = math.floor(-scr)
    if n_match != 12:
        continue
    print(f'  {wrds} {n_match}')


