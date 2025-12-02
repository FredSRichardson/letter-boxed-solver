#!/usr/bin/env python3

# This version uses a scrabble dictionary

import argparse, re
import openfst_python as fst

EPSILON_TOK = '<epsilon>'


def split_lb_side(astr):
    astr = astr.upper()
    ret = re.match(r'^\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*$', astr)
    if ret is None: 
        return None
    return ret.groups()

def make_lex_fst(lb_set, lb_wrds):
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

    wt_one = fst.Weight.One(lex_fst.weight_type())

    for wrd, wrd_set in lb_wrds:
        s_prev = s_start
        for ind, c in enumerate(wrd):
            s_new = lex_fst.add_state()
            ilbl = isyms.find(c)
            olbl = 0
            if ind == len(wrd) - 1:
                olbl = osyms.find(wrd)
            lex_fst.add_arc(s_prev, fst.Arc(ilbl, olbl, -len(wrd_set), s_new))
            s_prev = s_new
        lex_fst.add_arc(s_prev, fst.Arc(0, 0, wt_one, s_end))

    lex_fst.set_final(s_end)
    
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

    lb_fst.set_final(s_end)
    
    return lb_fst
    

parser = argparse.ArgumentParser(description='Solve the NYT Letter Boxed puzzle using a word list')
parser.add_argument('-v', '--verbose', action='store_true',
                    help='increase output verbosity')

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


print(f'Number of words loaded from "{args.word_list}": {len(lexicon)}')
            
# Get the set of all Letter Boxed letters:
lb_set = set(lb_t + lb_l + lb_r + lb_b)

# Get words that only contain letters in the Letter Boxed set:
lb_wrds = []
for wrd in sorted(lexicon):
    if len(wrd) < 3:
        continue
    wrd_set = set(wrd)
    if wrd_set - lb_set:
        continue
    rem_set = lb_set - wrd_set
    lb_wrds.append( (wrd, wrd_set) )

lex_fst = make_lex_fst(lb_set, lb_wrds)

lb_fst = make_lb_fst( [ lb_t, lb_l, lb_r, lb_b ], lex_fst)

lex_fst = fst.determinize(lex_fst)

res_fst = fst.compose(lb_fst, lex_fst)

nb_fst = fst.shortestpath(res_fst, nshortest=100).rmepsilon()

print('+++ Possible Letter Boxed solutions for puzzle:')
print(f'  LEFT:   {" ".join(lb_l)}')
print(f'  TOP:    {" ".join(lb_t)}')
print(f'  RIGHT:  {" ".join(lb_r)}')
print(f'  BOTTOM: {" ".join(lb_b)}')
print('')

print('+++ Single word coverage: ')
# Map of: 
# #unique-letters -> set-of-unique-letters -> shortest to longeest words
final_res = {}
flat_res = []
for nd in nb_fst.states():
    for arc in nb_fst.arcs(nd):
        if arc.olabel != 0:
            wrd = nb_fst.output_symbols().find(arc.olabel)
            wrd_set = set(wrd)
            n_uniq = len(wrd_set)
            if not n_uniq in final_res:
                final_res[n_uniq] = {}
            wrd_set_key = ' '.join(list(sorted(wrd_set)))
            if not wrd_set_key in final_res[n_uniq]:
                final_res[n_uniq][wrd_set_key] = []
            final_res[n_uniq][wrd_set_key].append(wrd)
            # print(f'{wrd} {len(wrd_set)}')
            flat_res.append( (wrd, wrd_set) )

for n_uniq in sorted(final_res, key=lambda x: -x):
    for wrd_set in final_res[n_uniq]:
        print(f'  number-letters: {n_uniq}, letters: {wrd_set}:')
        for wrd in sorted(final_res[n_uniq][wrd_set], key=lambda x: len(x)):
            print(f'    {wrd} len={len(wrd)}')

print('')
print('+++ Word pair coverage: ')
pair_res = {}
for wrd, wrd_set in flat_res:
    for wrd2, wrd_set2 in flat_res:
        if wrd == wrd2: continue
        if wrd[-1] != wrd2[0]: continue
        tot_set = wrd_set | wrd_set2
        n_uniq = len(tot_set)
        if not n_uniq in pair_res:
            pair_res[n_uniq] = {}
        wrd_set_key = ' '.join(list(sorted(tot_set)))
        if not wrd_set_key in pair_res[n_uniq]:
            pair_res[n_uniq][wrd_set_key]= []
        pair_res[n_uniq][wrd_set_key].append(wrd + ' ' + wrd2)

for n_uniq in sorted(pair_res, key=lambda x: -x):
    for wrd_set in pair_res[n_uniq]:
        print(f'  number-letters: {n_uniq}, letters: {wrd_set}:')
        for wrd in sorted(pair_res[n_uniq][wrd_set], key=lambda x: len(x)):
            print(f'    {wrd} len={len(wrd)}')

print('')

