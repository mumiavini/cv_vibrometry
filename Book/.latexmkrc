# latexmk configuration for the TCC.
# Goal: keep all the noisy build artifacts (.aux, .log, .fls, .fdb_latexmk,
# .synctex.gz, .bbl, .blg, .out, ...) in a single ./build/ folder instead of
# scattering them next to the .tex, while the final PDF still lands next to
# the .tex (Book/TCC....pdf).

$pdf_mode = 1;          # build a PDF via pdflatex
$bibtex_use = 2;        # run bibtex as needed (and clean .bbl on cleanup)

# bibtex runs inside $aux_dir (build/), so point it back at the source dir
# (absolute path to this .latexmkrc's folder) so it can find referencias.bib
# and any .bst styles. Trailing '' keeps the default search paths too.
# bibtex/pdflatex run inside $aux_dir (build/), so they must be told where the
# source dir is. On this MiKTeX + git-bash setup, MiKTeX needs a NATIVE Windows
# path (C:/...) with ';' separators, not the /c/... msys path getcwd() returns.
use Cwd 'getcwd';
my $srcdir = getcwd();                       # e.g. /c/soft/.../Book
$srcdir =~ s{^/([a-zA-Z])/}{\U$1\E:/};       # -> C:/soft/.../Book
$ENV{'BIBINPUTS'} = "$srcdir;";
$ENV{'BSTINPUTS'} = "$srcdir;";
$ENV{'TEXINPUTS'} = "$srcdir;";

# All intermediate/aux files go here; the PDF goes next to the source.
$aux_dir = 'build';
$out_dir = '.';

# Generate a SyncTeX file (for editor <-> PDF sync); it lands in aux_dir.
set_tex_cmds('-synctex=1 -interaction=nonstopmode -file-line-error %O %S');

# Files latexmk should also remove on `latexmk -c` / `-C`.
push @generated_exts, 'synctex.gz', 'fls', 'fdb_latexmk', 'run.xml', 'bcf';
$clean_ext = 'synctex.gz synctex.gz(busy) run.xml bcf';
