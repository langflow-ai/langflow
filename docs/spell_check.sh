# Using cspell, we'll loop over each subdirectory inside ./docs and check every mdx file for spelling errors.
# If there is an error, we'll write the word to an output file

# prep
if [ -f spell_check_results.txt ]; then
  rm spell_check_results.txt
fi
cd docs

# first check, over the mdx files in the root directory
find . -maxdepth 1 -type f -name "*.mdx" -exec cspell --words-only {} \; >> ../output.txt

# loop over each subdirectory and any directories inside
for dir in */; do
  find $dir -type d -exec cspell --words-only {}/*.mdx \; >> ../output.txt
done

# loop over each line in the output file and prune duplications
cd ../
awk '!a[$0]++' output.txt > spell_check_results.txt
rm output.txt

# check the number of lines in spell_check_results.txt
lines=$(wc -l < spell_check_results.txt)

echo "There are $lines spelling errors or unknown words."