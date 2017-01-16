#!/bin/bash
# needs summary.x from ert, gnuplot, and pdflatex

#Stop on first error
#set -e

#set -x


usage() { 
  #Grep through this source file for the options
  echo "$0 usage:" && grep "    .)\ # " $0
  exit 1
}


OUTFILE=
DECK=
RUNS=
KEYS=
WELLS=
CLEAN_UP=
[ $# -eq 0 ] && usage
while getopts "o:d:r:v:w:ch" arg; do
  case $arg in
    o) # Output filename
      echo "OUT ${OPTARG}"
      OUTFILE=${OPTARG}
      ;;
    d) # Deck filename
      echo "DECK ${OPTARG}"
      DECK=${OPTARG}
      ;;
    r) # Individual runs to plot
      echo "RUNS ${OPTARG}"
      RUNS="${RUNS} ${OPTARG}"
      ;;
    v) # Variables / keys to plot for each well (e.g., WBHP WOPR WGFR WWPR)
      echo "KEYS ${OPTARG}"
      KEYS="${KEYS} ${OPTARG}"
      ;;
    w) # Wells to plot for each run (leave empty for all)
      echo "Wells: ${OPTARG}"
      WELLS="${WELLS} ${OPTARG}"
      ;;
    c) # Clean up by deleting temp files
      echo "Cleaning up set"
      CLEAN_UP=true
      ;;
    h) # Display help.
      usage
      exit 0
      ;;
  esac
done


if [ -z "$OUTFILE" ]; then echo "No outfile" && usage; fi
if [ -z "$DECK" ]; then echo "No deck" && usage; fi
if [ -z "$RUNS" ]; then echo "No runs" && usage; fi
if [ -z "$KEYS" ]; then echo "No keys" && usage; fi
#No wells is OK, plot all


# this requires the summary.x binary from ert
# Either
if [ ! -x "$SUMMARY_X" ]; then
  SUMMARY_X=summary.x
fi

if [ "`type -t \"$SUMMARY_X\"`" != "file" ]; then
  echo "Could not find summary.x"
  echo "Make sure summary.x is on path, or set the"
  echo "environment variable SUMMARY_X"
  exit 1
fi





TEMPDIR=`mktemp -d`
CURRENTDIR=`pwd`

# Get a list of all possible wells for each deck
if [ -z "$WELLS" ]; then
  for RUN in $RUNS; do
    DECKNAME=$RUN/$DECK
    echo "Finding wells in " $DECKNAME

    # Loop over all the keys, and find wells
    ALLKEYS=`$SUMMARY_X --list $DECKNAME`
    for WELL_CANDIDATE in $ALLKEYS; do
      KEY=`echo $WELL_CANDIDATE | grep WBHP | grep -v WBHPH`

      # Only store wells
      if [ "$KEY" != "" ] ; then
        echo "Found $KEY"
        KEY=`echo $KEY | cut -d ":" -f 2`
        WELLS="$WELLS $KEY"
      fi
    done
  done

  # Make sure the list of wells is unique
  WELLS=`echo $WELLS | tr " " "\n" | sort | uniq`
fi



# Create a temp directory for each run
for RUN in $RUNS; do
  RUNTEMPDIR=$TEMPDIR/$RUN
  echo "Creating temp dir $RUNTEMPDIR"
  mkdir -p "$RUNTEMPDIR"
done


# generate a data file for each well for all specified keys (opts)
for RUN in $RUNS; do
  RUNTEMPDIR=$TEMPDIR/$RUN

  for WELL in $WELLS ; do
    GNUPLOT_OUTFILE="$RUNTEMPDIR/$WELL.gnu"
    echo "Creating file $GNUPLOT_OUTFILE"

    #Set options for summary.x
    WELLOPTS=
    for KEY in $KEYS; do
      WELLOPTS="$WELLOPTS $KEY:$WELL"
    done

    # Run summary.x to extract data in gnuplot-friendly format
    $SUMMARY_X "$RUN/$DECK" $WELLOPTS > $GNUPLOT_OUTFILE
  done
done


# Use Gnuplot to plot each option/variable
for WELL in $WELLS ; do
  COLUMN=3 # Column 1 is days, 2 is date, then one column per option in datafiles

  for KEY in $KEYS; do
    #Main plot file for Gnuplot
    PLOTFILE="$TEMPDIR/well-${WELL}-${KEY}.gnu"

    # General Gnuplot options
    echo "set terminal postscript color" > $PLOTFILE
    echo "set output \"$TEMPDIR/well-${WELL}-${KEY}.eps\"" >> $PLOTFILE
    echo "set xlabel \"days\"" >> $PLOTFILE
    echo "set ylabel \"$KEY\"" >> $PLOTFILE
    echo "set grid" >> $PLOTFILE

    # Create a plot for each run (for comparison)
    LINECOLOR=1
    LINEWIDTH=3
    FIRST_ITER=true
    PLOT_COMMAND=
    for RUN in $RUNS; do
      RUNTEMPDIR=$TEMPDIR/$RUN

      # Comma to separate lines
      if [ "$PLOT_COMMAND" != "" ]; then
        PLOT_COMMAND="$PLOT_COMMAND,"
        LINECOLOR=`expr $LINECOLOR + 2`
      else
        PLOT_COMMAND="plot"
      fi

      title=`echo $RUN | tr _ -`
      PLOT_COMMAND="$PLOT_COMMAND \"${RUNTEMPDIR}/$WELL.gnu\" \
        using 1:${COLUMN} \
        title \"$title\" \
        with lines \
        linewidth $LINEWIDTH \
        linecolor $LINECOLOR"
    done
    echo "$PLOT_COMMAND" >> $PLOTFILE

    # Run Gnuplot
    gnuplot $PLOTFILE

    # Move to next column/option
    COLUMN=`expr $COLUMN + 1`
  done
done




# Finally generate a latex-file report
PICCOUNT=1 
TEXFILE="$TEMPDIR/article.tex"
echo "
\\documentclass{article}
\\usepackage{graphicx}
\\setlength{\\hoffset}{0cm}
\\setlength{\\topmargin}{0.5cm}
\\setlength{\\headsep}{0cm}
\\setlength{\\headheight}{0cm}
\\setlength{\\textheight}{23cm}
\\setlength{\\textwidth}{15.5cm}
\\setlength{\\evensidemargin}{0.48cm}
\\setlength{\\oddsidemargin}{0.0cm}
" > $TEXFILE

echo "\\begin{document}" >> $TEXFILE
for WELL in $WELLS ; do
  for KEY in $KEYS; do
    echo "\\begin{figure}" >> $TEXFILE
    echo "\\rotatebox{270}{\\includegraphics[width=0.65\\textwidth]{well-$WELL-$KEY}}\\\\" >> $TEXFILE
    echo "\\caption{$KEY of well \\textbf{$WELL}.}" >> $TEXFILE
    echo "\\end{figure}" >> $TEXFILE
    if [ "`expr $PICCOUNT % 2`" == "0" ] || [ ]; then
      echo "\\clearpage" >> $TEXFILE
    fi
    PICCOUNT=`expr $PICCOUNT + 1`
  done
done
echo "\\end{document}" >> $TEXFILE

LATEXOPTS="--output-directory ${TEMPDIR} --interaction=nonstopmode -jobname=article"
LATEXCMD="latex $LATEXOPTS $TEXFILE"
cd $TEMPDIR && $LATEXCMD && $LATEXCMD
dvipdf article.dvi article.pdf
cd $CURRENTDIR
OUTDIR=`dirname "${OUTFILE}"`
mkdir -p "$OUTDIR"
mv "$TEMPDIR/article.pdf" "${OUTFILE}" && echo "Created ${OUTFILE}"


# remove temporary files
if [ ! -z "$CLEAN_UP" ]; then
  echo "Removing temporary files in $TEMPDIR"
  find $TEMPDIR -iname '*.eps' -exec rm {} +
  find $TEMPDIR -iname '*.gnu' -exec rm {} +
  rm "$TEMPDIR/article.dvi" "$TEMPDIR/article.log" "$TEMPDIR/article.aux" "$TEXFILE"
  for RUN in $RUNS; do
    RUNTEMPDIR=$TEMPDIR/$RUN
    rm -d $RUNTEMPDIR
  done

  echo "Files not removed: "
  find $TEMPDIR
else
  echo "Files left in $TEMPDIR"
fi
