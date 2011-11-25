#!/usr/bin/env bash
#
# Run in the main patrex directory to run tests

success=0
total=0

for patrex in $( ls tests/*.patrex ); do
	infile=${patrex/.patrex/.in}
	outfile=${patrex/.patrex/.out}
	if [[ -f ${outfile} && -f ${infile} ]]; then
		report=$(./patrex ${patrex} ${infile} 2> /dev/null | diff -uN ${outfile} - | tail -n +3)
		if [[ $report == "" ]]; then
			success=$((success+1))
		else
			echo "-------------------------"
			echo "FAILURE: ${patrex}"
			echo "${report}"
		fi
	else
		echo "-------------------------"
		echo "FAILURE: ${patrex}"
		if [[ ! -f ${infile} ]]; then
			echo "  Input file ${infile} missing"
		fi
		if [[ ! -f ${outfile} ]]; then
			echo "  Expected output file ${outfile} missing"
		fi
	fi
	total=$((total+1))
done

echo "-------------------------------------------"
echo "${success} OUT OF ${total} TEST SUCCESSFUL."
