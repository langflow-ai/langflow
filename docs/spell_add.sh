for line in $(cat spell_check_results.txt); do
  echo "Adding $line to cspell.config.yaml"
  echo "  - $line" >> cspell.config.yaml
done