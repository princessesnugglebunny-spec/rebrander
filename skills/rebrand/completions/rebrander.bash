# Bash completion for rebrander scripts
# Source: source /path/to/rebrander/completions/rebrander.bash

_rebrander_complete() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Common options
    opts="--brand --root --out --json --version --help --diff --dry-run --apply"

    case "$prev" in
        --brand)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        --root|--out|--diff-out|--manifest|--config)
            COMPREPLY=( $(compgen -d -- "$cur") )
            return 0
            ;;
    esac

    # Script-specific options
    local script="${COMP_WORDS[0]}"
    case "$script" in
        *brand-replace.py)
            opts="$opts --transactional --exclude --skip-dir --progress --diff-out --manifest --config"
            ;;
        *inventory.py)
            opts="$opts --workers --progress"
            ;;
        *artifact-scan.py)
            opts="$opts --token --artifacts --deep"
            ;;
        *binary-diff.py)
            opts="$opts --before --after --seed-va --seed-name"
            ;;
        *rubric-score.py)
            opts="$opts --artifacts --build-passed --tests-passed --inventory-coverage --auto --config"
        *source-scan.py)
            opts="$opts --brand --token --todo"
        *rebrand-run.py)
            opts="$opts --apply --fast --resume --state"
        *report.py)
            opts="$opts --artifacts --build-passed --tests-passed --inventory-coverage --baseline"
            ;;
        *gen-assets.py)
            opts="$opts --assets-dir --swap-colors"
            ;;
        *benchmark.py)
            opts="$opts --repos --workdir --csv"
            ;;
        *removal-log.py)
            opts="$opts --removed --reason --scan"
            ;;
        *revert.py)
            opts="$opts --branch --stash --file --list"
            ;;
        *rename-pack.py)
            opts="$opts --mode"
            ;;
        *state.py)
            opts="$opts init set get step show clear"
            ;;
        *merge-preflight.py)
            opts="$opts --repos"
            ;;
    esac

    COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
    return 0
}

# Register completion for all scripts
for script in brand-replace.py inventory.py artifact-scan.py binary-diff.py \
              rubric-score.py gen-assets.py benchmark.py removal-log.py \
              revert.py rename-pack.py ast-rename.py state.py merge-preflight.py; do
    complete -F _rebrander_complete "$script" 2>/dev/null
done