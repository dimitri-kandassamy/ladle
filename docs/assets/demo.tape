# demo.tape — renders docs/assets/demo.gif with VHS (https://github.com/charmbracelet/vhs)
#
# One-time setup:
#   brew install charmbracelet/tap/vhs      # or: see the VHS README for your OS
#   brew install pango poppler pandoc       # ladle's runtime tools (Java optional, for epubcheck)
#   pip install -e .                        # install `ladle` from a repo checkout
#
# Generate the GIF (from the repo root, with `ladle` on your PATH):
#   vhs docs/assets/demo.tape               # writes docs/assets/demo.gif
#

Require ladle

Output docs/assets/demo.gif

# Record in a plain bash shell so your personal zsh prompt (oh-my-zsh / p10k)
# never loads. p10k is zsh-only, so bash sidesteps the leaking prompt entirely.
Set Shell "bash"

# Window: sized to reveal the mint-tea recipe without scrolling it off, with small
# padding so the first line sits near the top edge.
Set FontSize 16
Set Width 1000
Set Height 680
Set Padding 16
Set Theme "Catppuccin Mocha"
Set TypingSpeed 55ms

# Hidden setup: clean branded prompt + point ladle at the example book.
Hide
Type `export PS1="\[\e[38;5;79m\]$\[\e[0m\] "`
Enter
Type "unset PROMPT_COMMAND"
Enter
Type "export BOOK_CONFIG=examples/the-ladle-kitchen/book.yaml"
Enter
Type "cd examples/the-ladle-kitchen"
Enter
Type "clear"
Enter
Show

Sleep 600ms

# 1 — recipes are just a folder of markdown
Type "# a folder of markdown recipes:"
Enter
Sleep 700ms
Type "ls recipes/"
Enter
Sleep 1.5s

# 2 — reveal one recipe: plain text, a little front matter
Type "# each one is plain text:"
Enter
Sleep 700ms
Type "cat recipes/mint-tea.md"
Enter
Sleep 4s

# Hidden setup: change directory to execute ladle commands
Hide
Type "cd ../.."
Enter
Type "clear" 
Enter
Show

# 3 — one command builds a print PDF *and* a reflowable EPUB
Type "# one command -> a print PDF and an ebook:"
Enter
Sleep 700ms
Type "ladle build"
Enter
Sleep 6s

# 4 — validate: schema + PDF structure + epubcheck + contact sheet
Type "# ...validated end to end:"
Enter
Sleep 700ms
Type "ladle validate"
Enter
Sleep 15s

# 5 — the artifacts, ready to publish
Type "# EPUB and PDF, ready to publish:"
Enter
Sleep 700ms
Type "ls -lh build/"
Enter
Sleep 3.5s
