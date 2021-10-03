"""
Classes for analysis of data produced by MCMC.

:Author:
    Eric Huang
"""

from typing import List
import numpy as np
import pandas as pd
from .controllers import DataManager


class SimpleAnalysis:

    data_dir: str
    data_manager: DataManager
    observable_names: List[str]
    independent_variables: List[str]
    results_df: pd.DataFrame
    inputs_df: pd.DataFrame
    estimates: pd.DataFrame

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.data_manager = DataManager(data_dir)

    def analyse(self):
        self.combine_inputs()
        self.combine_results()
        self.estimate_observables()
        self.estimate_correlation_length()

    def combine_results(self):
        """Combine all raw results in as single DataFrame."""
        summary = self.data_manager.load('results')
        entries = []
        for result in summary:
            entry = {
                k: v for k, v in result.items()
                if k in ['hash', 'seed', 'tau']
            }
            for name, values in result['observables'].items():
                entry[name] = values['total']/values['count']
            entry.update(result['sweep_stats'])
            entries.append(entry)
        results_df = pd.DataFrame(entries)
        self.results_df = results_df

        self.observable_names = list(summary[0]['observables'].keys())

    def combine_inputs(self):
        """Combine all input files in a single DataFrame."""
        inputs_df = pd.DataFrame(self.data_manager.load('inputs'))
        inputs_df = inputs_df.drop('disorder', axis=1)
        for k in ['disorder_params', 'spin_model_params']:
            inputs_df = pd.concat([
                inputs_df[k].apply(pd.Series),
                inputs_df.drop(k, axis=1)
            ], axis=1)

        self.independent_variables = list(
            inputs_df.columns.drop(['disorder_model', 'hash', 'spin_model'])
        ) + ['tau']
        self.inputs_df = inputs_df

    def estimate_observables(self):
        """Calculate estimators and uncertainties for observables."""
        df = self.inputs_df.merge(self.results_df)

        # Uncertainties and estimates for each observable.
        estimates = pd.DataFrame()
        for label in self.observable_names:
            estimates = pd.concat([
                estimates,
                pd.DataFrame({
                    f'{label}_estimate': df.groupby(
                        self.independent_variables
                    )[label].mean(),
                    f'{label}_uncertainty': df.groupby(
                        self.independent_variables
                    )[label].std(),
                    f'{label}_n_disorders': df.groupby(
                        self.independent_variables
                    )[label].count(),
                })
            ], axis=1)
        self.estimates = estimates.reset_index()

    def estimate_correlation_length(self, n_resamp: int = 100):

        # Generator for bootstrapping.
        bs_rng = np.random.default_rng(0)
        estimates = self.estimates
        k_min = 2*np.pi/estimates[['L_x', 'L_y']].max(axis=1)
        estimates['CorrelationLength_estimate'] = 1/(
            2*np.sin(k_min/2)
        )*np.sqrt(np.abs(
            estimates['Susceptibility0_estimate']
            / estimates['Susceptibilitykmin_estimate']
            - 1
        ))
        uncertainty = np.zeros(estimates.shape[0])

        for i_row, row in self.estimates.iterrows():
            parameters = row[self.independent_variables].drop('tau')

            # Hashes for disorder configurations matching row parameters.
            hashes = self.inputs_df[
                (self.inputs_df[parameters.index] == parameters).all(axis=1)
            ]['hash'].values

            # Raw results filtered by matching disorders and tau.
            filtered_results = self.results_df[
                self.results_df['hash'].isin(hashes)
                & (self.results_df['tau'] == row['tau'])
            ].set_index('hash')

            resampled_correlation_lengths = np.zeros(n_resamp)

            # Perform resampling n_resamp times and calculate correlation
            # length using resampled results.
            for i_resamp in range(n_resamp):
                resampled_hashes = bs_rng.choice(hashes, size=hashes.size)
                susceptibility0_disorder_mean = filtered_results.loc[
                    resampled_hashes
                ]['Susceptibility0'].mean()
                susceptibilitykmin_disorder_mean = filtered_results.loc[
                    resampled_hashes
                ]['Susceptibilitykmin'].mean()
                resampled_correlation_lengths[i_resamp] = 1/(
                    2*np.sin(k_min[i_row]/2)
                )*np.sqrt(np.abs(
                    susceptibility0_disorder_mean
                    / susceptibilitykmin_disorder_mean
                    - 1
                ))

            uncertainty[i_row] = resampled_correlation_lengths.std()

        estimates['CorrelationLength_uncertainty'] = uncertainty