import os
import re
from collections import Counter
from itertools import groupby
from subprocess import Popen, PIPE
from contextlib import contextmanager

@contextmanager
def working_directory(path):
    prev_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)

def load_repo(filename):
    if not os.path.isdir(os.path.join(filename, '.git')):
        raise ValueError('not a git repo')
    with working_directory(filename):
        output, err = Popen(['git', 'log', "--pretty='%h|%p|%s'", "--date-order"], stdout=PIPE).communicate()

    commits = []
    messages = {}
    parents = {}
    for line in output.split('\n'):
        if not line:
            continue
        m = re.search(r"'(?P<hash>\w+)[|](?P<parents>(?:\w+[ ])*(?:\w+)?)[|](?P<message>.*)'", line)
        commits.append(m.group('hash'))
        messages[m.group('hash')] = m.group('message')
        parents[m.group('hash')] = m.group('parents').split()

    commits.reverse()

    return commits, reversed(parents), messages


def parents(node, children):
    return reversed(children).get(node, {})

def reversed(d):
    rev = {}
    for parent, children in d.iteritems():
        for child in children:
            if child in rev:
                rev[child].append(parent)
            else:
                rev[child] = [parent]
    return rev


def merge(columns, parents, name):
    """Removes one of each of name's parents and add name"""
    assert len(parents) > 0
    new = []
    parents_merged = []
    node_written = False
    for col in columns:
        if col in parents:
            if col in parents_merged:
                new.append(col)
                continue
            parents_merged.append(col)
            if not node_written:
                new.append(name)
                node_written = True
        else:
            new.append(col)
    assert sorted(parents) == sorted(parents_merged), '%r %r %r %r %r' % (columns, parents, name, sorted(parents), sorted(parents_merged))
    return new


def branch(columns, children, name):
    new = []
    for c in columns:
        if c == name:
            new.extend([name]*len(children))
        else:
            new.append(c)
    return new


def _ascii_split(splits):
    r"""Returns lines of ascii illustration
    Input should never cross
    Only one column should branch, but it could branch multiple times

    >>> _ascii_split(1)
    ['|\\']
    >>> for r in _ascii_split(2): print r
    |\
    | \
    | |\
    >>> for r in _ascii_split(3): print r
    |\
    | \
    | |\
    | | \
    | | |\
    """
    new = []
    for i in range(splits):
        new.append('| '*i + '|\\')
        if i == splits - 1:
            break
        new.append('| '*(i+1) + '\\')

    return new


def ascii_branch(start, finish):
    """Build lines of ascii branch

    >>> for r in ascii_branch([1], [1, 1]): print r
    |\\
    >>> for r in ascii_branch([1, 2, 3], [1, 2, 2, 3]): print r
    | |\\ \\
    """
    assert len(start) < len(finish)
    assert set(start) == set(finish)
    start_groups = [(k, len(list(v))) for k, v in groupby(start)]
    finish_groups = [(k, len(list(v))) for k, v in groupby(finish)]

    for i, ((k, c1), (k2, c2)) in enumerate(zip(start_groups, finish_groups)):
        assert k == k2
        if c1 == c2:
            continue
        else:
            assert c2 > c1
            before = sum(v for k, v in finish_groups[:i]) + c2 - c1 - 1
            after = sum(v for k, v in finish_groups[i+1:])
            break
    split = _ascii_split(c2 - c1)
    final = []
    for line in split:
        final.append(' '.join(['|'] * before + [line] + ['\\'] * after))
    return final


def _ascii_crossover(crosses):
    """

    >>> for r in _ascii_crossover(3): print r
    | | | |  \\
    | |_|_|__/
    |/| | |   
    | | | |  
    """
    lines = ['| ' + '| '*crosses + ' \\',
             '| ' + '|_'*crosses + '_/',
             '|/' + '| '*crosses + '  ',
             '| ' + '| '*crosses + ' ']
    return lines


def ascii_merge(start, finish):
    """Build lines of ascii merge

    Exactly one merge will occur, but it could be from multiple branches.

    >>> for r in ascii_merge([1, 1, 2], [1, 2]): print r
    |  \\ \\
    | _/ /
    |/  /
    |  /
    >>> for r in ascii_merge([1, 2, 1], [1, 2]): print r
    | |  \\
    | |__/
    |/|
    | |
    >>> for r in ascii_merge([1, 2, 2, 3, 1, 4], [1, 2, 2, 3, 4]): print r
    | | | |  \\ \\
    | |_|_|__/ /
    |/| | |   /
    | | | |  /
    """
    assert len(start) - 1 == len(finish), 'for now only 2-way merges allowed: %r %r' % (start, finish)
    #TODO Special case simple merge when no crossing over required

    (merged,) = (Counter(start) - Counter(finish)).keys()

    dest = finish.index(merged)
    assert dest == start.index(merged), '%r %r (%r)' % (start, finish, merged)
    origin = dest + start[dest+1:].index(merged) + 1
    after = len(start) - origin - 1

    cross = _ascii_crossover(origin - dest - 1)
    lines = [
        '| '*dest + cross[0] + ' \\'*after,
        '| '*dest + cross[1] + ' /'*after,
        '| '*dest + cross[2] + '/ '*after,
        '| '*dest + cross[3] + '/ '*after
    ]
    lines = [line.rstrip() for line in lines]
    return lines


    start_groups = [(k, len(list(v))) for k, v in groupby(start)]
    finish_groups = [(k, len(list(v))) for k, v in groupby(finish)]

    for i, ((k, c1), (k2, c2)) in enumerate(zip(start_groups, finish_groups)):
        assert k == k2
        if c1 == c2:
            continue
        else:
            assert c2 > c1
            before = sum(v for k, v in finish_groups[:i]) + c2 - c1 - 1
            after = sum(v for k, v in finish_groups[i+1:])
            break


def format_line(name, columns, msg=None):
    return (' '.join(['o' if x == name else '|' for x in columns]) + '   ' + str(name) + (' '+msg if msg else ''))[:80]


def print_row(commit, children, columns=None, msg=None):
    if columns is None:
        print format_line(commit, [commit], msg)
        return [commit]

    if len(parents(commit, children)) == 0: # no parents!
        new = columns + [commit]
    else:
        new = merge(columns, parents(commit, children), commit)

    if len(parents(commit, children)) > 1:
        parents_merged = []
        pre_merge = []
        for c in columns:
            if c in parents(commit, children) and c not in parents_merged:
                parents_merged.append(c)
                pre_merge.append('to_merge')
            else:
                pre_merge.append(c)
        post_merge = [c if c in columns else 'to_merge'
                      for c in new]
        for line in ascii_merge(pre_merge, post_merge):
            print line

    print format_line(commit, new, msg)

    newer = branch(new, children.get(commit, []), commit)

    if len(children.get(commit, {})) > 1:
        for line in ascii_branch(new, newer):
            print line

    return newer

def print_lines(commits, children, messages={}):
    cols = print_row(commits[0], children, msg=messages.get(commits[0]))
    for commit in commits[1:]:
        cols = print_row(commit, children, cols, msg=messages.get(commit))


if __name__ == '__main__':
    import doctest
    if doctest.testmod()[0] == 0:
        print_lines(*load_repo('/Users/tomb/Dropbox/code/bpython'))
