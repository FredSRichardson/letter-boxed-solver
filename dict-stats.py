#!/usr/bin/env python3

import re

lexicon = set()

lb_top = 'IDM'
lb_lft = 'TLP'
lb_rit = 'RFE'
lb_bot = 'BOU'

with open('cmudict-0.7b.txt', 'r', encoding='latin-1') as ifp:
    for line in ifp:
        line = line.strip()
        if re.match(r'^\s*;.*$', line):
            continue
        e = line.split()
        assert len(e) > 1, f'ERROR: expect at least to tokens in line of dictionary: {line}'
        wrd = e[0]
        if re.match(r'^[^a-zA-Z].*$', wrd):
            continue
        ind = wrd.find('(')
        if ind >= 0:
            wrd = wrd[:ind]
        lexicon.add(wrd)

print(f'Number of words: {len(lexicon)}')
            
n_comp = 0
for wrd in lexicon:
    if wrd.find('_') >= 0:
        n_comp += 1

print(f'Number of compound words: {n_comp}')

with open('cmudict-0.7b-clean.txt', 'w') as ofp:
    for wrd in sorted(lexicon):
        if not re.match(r'^[A-Za-z]+$', wrd):
            continue
        ofp.write(f'{wrd}\n')
    
lb_set = set()
for c in lb_top + lb_lft + lb_rit + lb_bot:
    lb_set.add(c)

in_lb = []
for wrd in sorted(lexicon):
    if len(wrd) < 3:
        continue
    wrd_set = set(wrd)
    if wrd_set - lb_set:
        continue
    rem_set = lb_set - wrd_set
    in_lb.append( (wrd, wrd_set) )
    # break       # Debug

if False:
    for wrd, wrd_set in sorted(in_lb, key=lambda x: len(x[1])):
        print(f'{wrd}  {rem_set}')

import openfst_python as fst

lex_fst = fst.Fst()

isyms = fst.SymbolTable()
osyms = fst.SymbolTable()

# Epsilon should have index 0:
epsilon_lbl = '<epsilon>'
isyms.add_symbol(epsilon_lbl)
for c in lb_set:
    isyms.add_symbol(c)

osyms.add_symbol(epsilon_lbl)
for wrd, _ in in_lb:
    osyms.add_symbol(wrd)

assert isyms.find(epsilon_lbl) == 0, f'ERROR: "{epsilon_lbl}" in isyms does not have index 0 ({isyms.find(epsilon_lbl)})'
assert osyms.find(epsilon_lbl) == 0, f'ERROR: "{epsilon_lbl}" in osyms does not have index 0 ({osyms.find(epsilon_lbl)})'

lex_fst.set_input_symbols(isyms)
lex_fst.set_output_symbols(osyms)

s_start = lex_fst.add_state()
s_end = lex_fst.add_state()

lex_fst.set_start(s_start)

wt_one = fst.Weight.One(lex_fst.weight_type())

for wrd, wrd_set in in_lb:
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

lb_fst = fst.Fst()

s_start = lb_fst.add_state()
s_end = lb_fst.add_state()

lb_fst.set_input_symbols(isyms)
lb_fst.set_output_symbols(isyms)

lb_fst.set_start(s_start)

lb_sides = [ lb_top, lb_lft, lb_rit, lb_bot ]

lb_nodes = []
for iside in range(4):
    snodes = []
    for ic in lb_sides[iside]:
        snodes.append(lb_fst.add_state())
    lb_nodes.append(snodes)
    


for iside in range(4):
    inodes = []
    for iind, ic in enumerate(lb_sides[iside]):
        inode = lb_nodes[iside][iind]
        ilbl = isyms.find(ic)
        lb_fst.add_arc(s_start, fst.Arc(0, ilbl, wt_one, inode))
        lb_fst.add_arc(inode, fst.Arc(0, 0, wt_one, s_end))
        for jside in range(4):
            if iside == jside:
                continue
            for jind, jc in enumerate(lb_sides[jside]):
                jnode = lb_nodes[jside][jind]
                jlbl = isyms.find(jc)
                lb_fst.add_arc(inode, fst.Arc(0, jlbl, wt_one, jnode))
                
lb_fst.set_final(s_end)

# print(fst.determinize(lb_fst))

lex_fst = fst.determinize(lex_fst)

# print(lb_fst)
# print(lex_fst)

# print(fst.compose(lb_fst, lex_fst).rmepsilon())
res_fst = fst.compose(lb_fst, lex_fst)

# nb_fst = fst.shortestpath(res_fst, nshortest=1000)

nb_fst = fst.shortestpath(res_fst, nshortest=100).rmepsilon()

# print(res_fst)
final_res = []
for nd in nb_fst.states():
    for arc in nb_fst.arcs(nd):
        if arc.olabel != 0:
            wrd = osyms.find(arc.olabel)
            wrd_set = set(wrd)
            final_res.append( (wrd, wrd_set) )
            print(f'{wrd} {len(wrd_set)}')

print('')

pair_res = []
for wrd, wrd_set in final_res:
    for wrd2, wrd_set2 in final_res:
        if wrd == wrd2: continue
        if wrd[-1] != wrd2[0]: continue
        tot_set = wrd_set | wrd_set2
        pair_res.append( (wrd, wrd2, len(tot_set)) )

for wrd, wrd2, set_len in sorted(pair_res, key=lambda x: -x[2]):
    print(f'{wrd} {wrd2} {set_len}')

