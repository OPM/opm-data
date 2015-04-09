#!/bin/bash
# needs summary.x from ert, gnuplot, and pdflatex

# this requires the summary.x binary from ert (if not in search PATH)
SUMMARY_X=summary.x

OUTPUT=norne-wells

OPTS="WBHP WOPR WGPR WWPR"
DECK=NORNE_ATW2013

DIRS="ECL OPM"
WELLS="
B-1AH
B-1BH
B-1H
B-2H
B-3H
B-4AH
B-4BH
B-4DH
B-4H
C-1H
C-2H
C-3H
C-4AH
C-4H
D-1CH
D-1H
D-2H
D-3AH
D-3BH
D-3H
D-4AH
D-4H
E-1H
E-2AH
E-2H
E-3AH
E-3BH
E-3CH
E-3H
E-4AH
E-4H
F-1H
F-2H
F-3H
F-4H
K-3H"

# create a file for each well for all specified wells
for DIR in $DIRS; do
  if ! test -d $DIR ; then
    echo "ERROR: directory $DIR does not exist"
    exit 1
  fi
  for WELL in $WELLS ; do
    echo "Creating file $DIR/${WELL}.gnu"
    WELLOPTS=
    for OPT in $OPTS; do
      WELLOPTS="$WELLOPTS $OPT:$WELL"
    done
    $SUMMARY_X $DIR/$DECK $WELLOPTS > $DIR/$WELL.gnu
  done
done

WELLLISTEX=$OUTPUT-list.tex
echo "" > $WELLLISTEX

PLOTFILE=$OUTPUT.gnu

PICCOUNT=1 # 1 is days, 2 is date
for WELL in $WELLS ; do
  COUNT=3 # 1 is days, 2 is date
  for OPT in $OPTS; do
    echo "set terminal postscript color" > $PLOTFILE
    echo "set output \"well-${WELL}-${OPT}.eps\"" >> $PLOTFILE
    echo "set xlabel \"days\"" >> $PLOTFILE
    echo "set ylabel \"$OPT\"" >> $PLOTFILE
    echo "set grid" >> $PLOTFILE
    PLOTS=
    LC=1
    LW=4
    for DIR in $DIRS; do
      if [ "$PLOTS" != "" ]; then
        PLOTS="$PLOTS,"
        LC=`expr $LC + 2`
      fi
      PLOTS="$PLOTS \"${DIR}/$WELL.gnu\" u 1:${COUNT} title \"$DIR\" w l lw $LW lc $LC"
    done
    echo "plot $PLOTS" >> $PLOTFILE
    gnuplot $PLOTFILE

    echo "\\begin{figure}" >> $WELLLISTEX
    echo "\\rotatebox{270}{\\includegraphics[width=0.65\\textwidth]{well-$WELL-$OPT}}\\\\" >> $WELLLISTEX
    echo "\\caption{$OPT of well \\textbf{$WELL}.}" >> $WELLLISTEX
    echo "\\end{figure}" >> $WELLLISTEX
    if [ "`expr $PICCOUNT % 2`" == "0" ] || [ ]; then
      echo "\\clearpage" >> $WELLLISTEX
    fi
    COUNT=`expr $COUNT + 1`
    PICCOUNT=`expr $PICCOUNT + 1`
  done
done

WELLTEX=$OUTPUT.tex

echo "\\documentclass{article}" > $WELLTEX
echo "\\usepackage{graphicx}" >> $WELLTEX
echo "\\setlength{\\hoffset}{0cm}" >> $WELLTEX
echo "\\setlength{\\topmargin}{0.5cm}" >> $WELLTEX
echo "\\setlength{\\headsep}{0cm}" >> $WELLTEX
echo "\\setlength{\\headheight}{0cm}" >> $WELLTEX
echo "\\setlength{\\textheight}{23cm}" >> $WELLTEX
echo "\\setlength{\\textwidth}{15.5cm}" >> $WELLTEX
echo "\\setlength{\\evensidemargin}{0.48cm}" >> $WELLTEX
echo "\\setlength{\\oddsidemargin}{0.0cm}" >> $WELLTEX
echo "\\begin{document}" >> $WELLTEX
echo "\\input{$WELLLISTEX}" >> $WELLTEX
echo "\\end{document}" >> $WELLTEX

latex --interaction=nonstopmode $OUTPUT
latex --interaction=nonstopmode $OUTPUT
dvipdf $OUTPUT

# remove temporary files
rm -f $WELLLISTEX
rm -f $PLOTFILE
rm -f $WELLTEX $OUTPUT.aux $OUTPUT.log $OUTPUT.dvi
find . -name "well-*.eps" -exec rm {} \;
