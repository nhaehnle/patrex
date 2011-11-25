#!/usr/bin/env bash
#
# Run in the main patrex directory to run tests

success=0
total=0

for patrex in $( ls tests/*.patrex ); do
	infile=${patrex/.patrex/.in}
	outfile=${patrex/.patrex/.out}
	if report=$(diff -u <(./patrex ${patrex} ${infile}) ${outfile}); then
		success=$((success+1))
	else
		echo "FAILURE: ${patrex}"
		echo "${report}" | tail -n +3
		echo "-------------------------"
	fi
	total=$((total+1))
done

echo "${success} OUT OF ${total} TEST SUCCESSFUL."
