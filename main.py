import os
import re
from multiprocessing import Pool
from time import time

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
    with open(f'{path_to_test}/report.txt', 'w') as report:
        # Check ft_reference and ft_run existence
        path_to_ref_results = f'{path_to_test}/ft_reference/'
        path_to_run_results = f'{path_to_test}/ft_run/'
        valid = True
        if not os.path.isdir(path_to_run_results):
            report.write(f'directory missing: ft_run\n')
            valid = False
        if not os.path.isdir(path_to_ref_results):
            report.write(f'directory missing: ft_reference\n')
            valid = False
        if not valid:
            return valid

        # Check stdout match
        ref_results_as_list = sorted(os.listdir(path_to_ref_results))
        run_results_as_list = sorted(os.listdir(path_to_run_results))
        missing_in_run = set(ref_results_as_list).difference(run_results_as_list)
        missing_in_ref = set(run_results_as_list).difference(ref_results_as_list)
        if missing_in_run:
            report.write('In ft_run there are missing files present in ft_reference: ')
            report.write(', '.join(f'\'{i}/{i}.stdout\'' for i in sorted(missing_in_run)))
            report.write('\n')
            valid = False
        if missing_in_ref:
            report.write('In ft_run there are extra files not present in ft_reference: ')
            report.write(', '.join(f'\'{i}/{i}.stdout\'' for i in sorted(missing_in_ref)))
            report.write('\n')
            valid = False
        if not valid:
            return valid

        for i in ref_results_as_list:
            path_to_iteration_ref = f'{path_to_test}/ft_reference/{i}/{i}.stdout'
            path_to_iteration_run = f'{path_to_test}/ft_run/{i}/{i}.stdout'

            # Check ft_run for errors, get memory peak and bricks total
            max_peak_run, total_bricks_run, errors, solver = read_stdout(path_to_iteration_run, mode='run')
            if errors:
                for error in errors:
                    LINENO_INDEX = 0
                    LINE_INDEX = 1
                    lineno = error[LINENO_INDEX]
                    line = error[LINE_INDEX]
                    report.write(f'{i}/{i}.stdout({lineno}): {line}')
            if not solver:
                report.write(f'{i}/{i}.stdout: missing \'Solver finished at\'\n')

            # Get ft_reference memory peak and bricks total
            max_peak_ref, total_bricks_ref, _, _ = read_stdout(path_to_iteration_ref, mode='ref')

            # Verify memory peak and bricks total difference
            memory_diff = round((max_peak_run - max_peak_ref) / max_peak_ref, 2)
            bricks_diff = round((total_bricks_run - total_bricks_ref) / total_bricks_ref, 2)
            MAX_MEMORY_DIFF = 0.5
            MAX_BRICKS_DIFF = 0.1
            if abs(memory_diff) > MAX_MEMORY_DIFF:
                report.write(f'{i}/{i}.stdout: different \'Memory Working Set Peak\' '
                             f'(ft_run={max_peak_run}, ft_reference={max_peak_ref}, rel.diff={memory_diff:.2f}, criterion={MAX_MEMORY_DIFF})\n')
            if abs(bricks_diff) > MAX_BRICKS_DIFF:
                report.write(f'{i}/{i}.stdout: different \'Total\' of bricks '
                             f'(ft_run={total_bricks_run}, ft_reference={total_bricks_ref}, rel.diff={bricks_diff:.2f}, criterion={MAX_BRICKS_DIFF})\n')


if __name__ == '__main__':
    for experiment in os.listdir(LOGS_DIRECTORY):
        path_to_experiment = f'{LOGS_DIRECTORY}/{experiment}'
        tests = map(lambda test: f'{path_to_experiment}/{test}', os.listdir(path_to_experiment))  # proper paths to tests
        with Pool(os.cpu_count() // 2) as p:
            p.map(check_test, tests)

    # print reports
    for experiment in os.listdir(LOGS_DIRECTORY):
        path_to_experiment = f'{LOGS_DIRECTORY}/{experiment}'
        for test in os.listdir(path_to_experiment):
            path_to_test = f'{experiment}/{test}'
            path_to_report = f'{LOGS_DIRECTORY}/{path_to_test}/report.txt'
            with open(path_to_report, 'r') as report:
                report_contents = report.read()
                if not report_contents:
                    print(f'OK: {path_to_test}/')
                else:
                    print(f'FAIL: {path_to_test}/')
                    print(report_contents, end='')
