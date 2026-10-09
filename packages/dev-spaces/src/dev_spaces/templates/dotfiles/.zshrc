# dev-spaces container .zshrc
# Edit ~/.config/dev-spaces/dotfiles/.zshrc on the Mac; copied in when a container is created.

export PATH="$HOME/.local/bin:$HOME/.pixi/bin:$PATH"
export EDITOR=vim

HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt inc_append_history share_history

autoload -Uz compinit && compinit
autoload -Uz vcs_info
precmd() { vcs_info }
zstyle ':vcs_info:git:*' formats ' (%b)'
setopt prompt_subst
PROMPT='%F{yellow}[${DEV_SPACE:-dev}]%f %F{cyan}%~%f%F{green}${vcs_info_msg_0_}%f %# '

[[ -f ~/.devrc ]] && source ~/.devrc
