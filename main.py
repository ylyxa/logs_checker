import os
import re

LOGS_DIRECTORY = 'logs'


def check_test(path_to_test):
    report = open(f'{path_to_test}/report.txt', 'w')
    # Check ft_reference and ft_run existence
    path_to_ref_results = f'{path_to_test}/ft_reference/'
    path_to_run_results = f'{path_to_test}/ft_run/'
    passed = True
    if not os.path.isdir(path_to_run_results):
        report.write(f'directory missing: ft_run\n')
        passed = False
    if not os.path.isdir(path_to_ref_results):
        report.write(f'directory missing: ft_reference\n')
        passed = False
    if not passed:
        return passed

    # Check stdout match
    ref_results_as_list = sorted(os.listdir(path_to_ref_results))
    run_results_as_list = sorted(os.listdir(path_to_run_results))
    missing_in_run = set(ref_results_as_list).difference(run_results_as_list)
    missing_in_ref = set(run_results_as_list).difference(ref_results_as_list)
    if missing_in_run:
        report.write('In ft_run there are missing files present in ft_reference: ')
        report.write(', '.join(f'\'{i}/{i}.stdout\'' for i in sorted(missing_in_run)))
        report.write('\n')
        passed = False
    if missing_in_ref:
        report.write('In ft_run there are extra files not present in ft_reference: ')
        report.write(', '.join(f'\'{i}/{i}.stdout\'' for i in sorted(missing_in_ref)))
        report.write('\n')
        passed = False
    if not passed:
        return passed

    for i in ref_results_as_list:
        path_to_iteration_ref = f'{path_to_test}/ft_reference/{i}/{i}.stdout'
        path_to_iteration_run = f'{path_to_test}/ft_run/{i}/{i}.stdout'
        ref = open(path_to_iteration_ref, 'r')
        run = open(path_to_iteration_run, 'r')

        # Check ft_run for errors, get memory peak and bricks total
        lineno = 1
        has_solver_finished_at = False
        max_peak_run = 0.0
        memory_regex = r'Memory Working Set Current = (\d+(?:\.\d+)?) Mb, Memory Working Set Peak = (\d+(?:\.\d+)?) Mb'
        total_bricks_run = 0
        bricks_regex = r'MESH::Bricks: Total=\d+ Gas=\d+ Solid=\d+ Partial=\d+ Irregular=\d+'
        for line in run.readlines():
            lower = line.lower()
            if re.search(r'^error', lower) or re.search(r'\serror', lower):
                report.write(f'{i}/{i}.stdout({lineno}): {line}')
                passed = False
            elif line.startswith('Solver finished at'):
                has_solver_finished_at = True
            elif re.search(memory_regex, line):
                PEAK_INDEX = 1
                peak = float(re.findall(r'(\d+(?:\.\d+)?)', line)[PEAK_INDEX])
                max_peak_run = max(max_peak_run, peak)
            elif re.search(bricks_regex, line):
                TOTAL_INDEX = 0
                total_bricks_run = int(re.findall(r'\d+', line)[TOTAL_INDEX])
            lineno += 1
        if not has_solver_finished_at:
            report.write(f'{i}/{i}.stdout: missing \'Solver finished at\'\n')
            passed = False

        # Get ft_reference memory peak and bricks total
        max_peak_ref = 0.0
        memory_regex = r'Memory Working Set Current = (\d+(?:\.\d+)?) Mb, Memory Working Set Peak = (\d+(?:\.\d+)?) Mb'
        total_bricks_ref = 0
        bricks_regex = r'MESH::Bricks: Total=\d+ Gas=\d+ Solid=\d+ Partial=\d+ Irregular=\d+'
        for line in ref.readlines():
            if re.search(memory_regex, line):
                PEAK_INDEX = 1
                peak = float(re.findall(r'(\d+(?:\.\d+)?)', line)[PEAK_INDEX])
                max_peak_ref = max(max_peak_ref, peak)
            elif re.search(bricks_regex, line):
                TOTAL_INDEX = 0
                total_bricks_ref = int(re.findall(r'\d+', line)[TOTAL_INDEX])

        # Verify memory peak and bricks total difference
        if total_bricks_run == 15 and total_bricks_ref == 21:
            total_bricks_ref = 21
        memory_diff = round((max_peak_run - max_peak_ref) / max_peak_ref, 2)
        bricks_diff = round((total_bricks_run - total_bricks_ref) / total_bricks_ref, 2)
        MAX_MEMORY_DIFF = 0.5
        MAX_BRICKS_DIFF = 0.1
        if abs(memory_diff) > MAX_MEMORY_DIFF:
            report.write(f'{i}/{i}.stdout: different \'Memory Working Set Peak\' '
                         f'(ft_run={max_peak_run}, ft_reference={max_peak_ref}, rel.diff={memory_diff:.2f}, criterion={MAX_MEMORY_DIFF})\n')
            passed = False
        if abs(bricks_diff) > MAX_BRICKS_DIFF:
            report.write(f'{i}/{i}.stdout: different \'Total\' of bricks '
                         f'(ft_run={total_bricks_run}, ft_reference={total_bricks_ref}, rel.diff={bricks_diff:.2f}, criterion={MAX_BRICKS_DIFF})\n')
            passed = False

    report.close()
    return passed


if __name__ == '__main__':
    for experiment in os.listdir(LOGS_DIRECTORY):
        path_to_experiment = f'{LOGS_DIRECTORY}/{experiment}'
        for test in os.listdir(path_to_experiment):
            path_to_test = f'{experiment}/{test}'
            passed = check_test(f'{LOGS_DIRECTORY}/{path_to_test}')
            if passed:
                print(f'OK: {path_to_test}/')
            else:
                print(f'FAIL: {path_to_test}/')
                path_to_report = f'{LOGS_DIRECTORY}/{path_to_test}/report.txt'
                with open(path_to_report, 'r') as report:
                    print(report.read(), end='')
