import argparse
from build_analysis_dataset import run as build
from descriptive_analysis import run as describe
from composite_index import run as composite
from topsis import run as topsis
from clustering import run as cluster
from sensitivity_analysis import run as sensitivity
from package_results import run as package

def run(*, regenerate_architecture=False):
    for label, function in [('Source audit and data gate', build), ('Descriptions', describe),
                            ('Composite', composite), ('TOPSIS', topsis), ('K-means', cluster),
                            ('Robustness', sensitivity)]:
        print(label, flush=True)
        function()
    print('Evidence packages', flush=True)
    package(regenerate_architecture=regenerate_architecture)
    print('Technical pipeline finished. Run notebook execution and output verification next.', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reproduce analysis; preserve the existing architecture image by default.')
    parser.add_argument('--regenerate-architecture', action='store_true',
                        help='Explicitly regenerate the architecture image during packaging.')
    run(regenerate_architecture=parser.parse_args().regenerate_architecture)
