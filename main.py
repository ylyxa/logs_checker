import os
import re
from multiprocessing import Pool

LOGS_DIRECTORY = 'logs'


def read_stdout(path, mode='ref'):
    """Check file for errors if run, get memory peak and bricks total"""
    with open(path) as file:
        lineno = 1
        has_solver_finished_at = False
        max_peak = 0.0
        memory_regex = r'Memory Working Set Current = (\d+(?:\.\d+)?) Mb, Memory Working Set Peak = (\d+(?:\.\d+)?) Mb'
        total_bricks = 0
        bricks_regex = r'MESH::Bricks: Total=(\d+) Gas=(\d+) Solid=(\d+) Partial=(\d+) Irregular=(\d+)'
        errors = []
        for line in file.readlines():
            lower = line.lower()
            error_match = re.search(r'^error|\serror', lower) if mode == 'run' else None
            memory_match = re.search(memory_regex, line)
            bricks_match = re.search(bricks_regex, line)
            if mode == 'run':
                if error_match:
                    errors.append((lineno, line))
                elif line.startswith('Solver finished at'):
                    has_solver_finished_at = True
            if memory_match:
                PEAK_INDEX = 2
                peak = float(memory_match.group(PEAK_INDEX))
                max_peak = max(max_peak, peak)
            elif bricks_match:
                TOTAL_INDEX = 1
                total_bricks = int(bricks_match.group(TOTAL_INDEX))
            lineno += 1
    return max_peak, total_bricks, errors, has_solver_finished_at


def check_test(path_to_test):
    report = ''

    # Check ft_reference and ft_run existence
    path_to_ref_results = f'{LOGS_DIRECTORY}/{path_to_test}/ft_reference/'
    path_to_run_results = f'{LOGS_DIRECTORY}/{path_to_test}/ft_run/'
    passed = True
    if not os.path.isdir(path_to_run_results):
        report += f'directory missing: ft_run\n'
        passed = False
    if not os.path.isdir(path_to_ref_results):
        report += f'directory missing: ft_reference\n'
        passed = False
    if not passed:
        return passed, path_to_test, report

    # Check stdout match
    ref_results_as_list = sorted(os.listdir(path_to_ref_results))
    run_results_as_list = sorted(os.listdir(path_to_run_results))
    missing_in_run = set(ref_results_as_list).difference(run_results_as_list)
    missing_in_ref = set(run_results_as_list).difference(ref_results_as_list)
    if missing_in_run:
        report += 'In ft_run there are missing files present in ft_reference: '
        report += ', '.join(f'\'{i}/{i}.stdout\'' for i in sorted(missing_in_run))
        report += '\n'
        passed = False
    if missing_in_ref:
        report += 'In ft_run there are extra files not present in ft_reference: '
        report += ', '.join(f'\'{i}/{i}.stdout\'' for i in sorted(missing_in_ref))
        report += '\n'
        passed = False
    if not passed:
        return passed, path_to_test, report

    for i in ref_results_as_list:
        path_to_iteration_ref = f'{LOGS_DIRECTORY}/{path_to_test}/ft_reference/{i}/{i}.stdout'
        path_to_iteration_run = f'{LOGS_DIRECTORY}/{path_to_test}/ft_run/{i}/{i}.stdout'

        # Check ft_run for errors, get memory peak and bricks total
        max_peak_run, total_bricks_run, errors, solver = read_stdout(path_to_iteration_run, mode='run')
        if errors:
            for error in errors:
                LINENO_INDEX = 0
                LINE_INDEX = 1
                lineno = error[LINENO_INDEX]
                line = error[LINE_INDEX]
                report += f'{i}/{i}.stdout({lineno}): {line}'
                passed = False
        if not solver:
            report += f'{i}/{i}.stdout: missing \'Solver finished at\'\n'
            passed = False

        # Get ft_reference memory peak and bricks total
        max_peak_ref, total_bricks_ref, _, _ = read_stdout(path_to_iteration_ref, mode='ref')

        # Verify memory peak and bricks total difference
        memory_diff = round((max_peak_run - max_peak_ref) / max_peak_ref, 2)
        bricks_diff = round((total_bricks_run - total_bricks_ref) / total_bricks_ref, 2)
        MAX_MEMORY_DIFF = 0.5
        MAX_BRICKS_DIFF = 0.1
        if abs(memory_diff) > MAX_MEMORY_DIFF:
            report += f'{i}/{i}.stdout: different \'Memory Working Set Peak\' ' \
                      f'(ft_run={max_peak_run}, ft_reference={max_peak_ref}, rel.diff={memory_diff:.2f}, criterion={MAX_MEMORY_DIFF})\n'
            passed = False
        if abs(bricks_diff) > MAX_BRICKS_DIFF:
            report += f'{i}/{i}.stdout: different \'Total\' of bricks ' \
                      f'(ft_run={total_bricks_run}, ft_reference={total_bricks_ref}, rel.diff={bricks_diff:.2f}, criterion={MAX_BRICKS_DIFF})\n'
            passed = False
    return passed, path_to_test, report


if __name__ == '__main__':
    for experiment in os.listdir(LOGS_DIRECTORY):
        path_to_experiment = f'{LOGS_DIRECTORY}/{experiment}'
        tests = map(lambda test: f'{experiment}/{test}', os.listdir(path_to_experiment))
        with Pool(os.cpu_count() // 2) as p:
            for passed, path_to_test, report in p.imap(check_test, tests):
                with open(f'{LOGS_DIRECTORY}/{path_to_test}/report.txt', 'w') as report_file:
                    report_file.write(report)
                if passed:
                    print(f'OK: {path_to_test}/')
                else:
                    print(f'FAIL: {path_to_test}/')
                    print(report, end='')
