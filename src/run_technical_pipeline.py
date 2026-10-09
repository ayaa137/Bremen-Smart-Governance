from build_analysis_dataset import run as build
from descriptive_analysis import run as describe
from composite_index import run as composite
from topsis import run as topsis
from clustering import run as cluster
from sensitivity_analysis import run as sensitivity
from package_results import run as package

def run():
    for label, function in [('Source audit and data gate', build), ('Descriptions', describe),
                            ('Composite', composite), ('TOPSIS', topsis), ('K-means', cluster),
                            ('Robustness', sensitivity), ('Architecture and evidence packages', package)]:
        print(label, flush=True)
        function()
    print('Technical pipeline finished. Run notebook execution and output verification next.', flush=True)

if __name__ == '__main__':
    run()
