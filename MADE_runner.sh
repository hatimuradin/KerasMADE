#!/bin/bash
rm -f datasets/grid*
rm -f results/loss*

HEIGHT=4
WIDTH=4
TRAINSAMPLES=300
VALIDSAMPLES=1000
TESTSAMPLES=5000

python ./datasets/dataset_gen_grid.py $HEIGHT $WIDTH $TRAINSAMPLES $VALIDSAMPLES $TESTSAMPLES
DATASET="datasets/grid_${HEIGHT}x${WIDTH}_${TRAINSAMPLES}${VALIDSAMPLES}${TESTSAMPLES}.npz"

ORIG_PATH="./results/loss_${TRAINSAMPLES}${VALIDSAMPLES}${TESTSAMPLES}_orig.txt"
python kerasMADE_orig.py $DATASET orig > $ORIG_PATH
PROPOSED_PATH="./results/loss_${TRAINSAMPLES}${VALIDSAMPLES}${TESTSAMPLES}_proposed.txt"
python kerasMADE_orig.py $DATASET minus > $PROPOSED_PATH
