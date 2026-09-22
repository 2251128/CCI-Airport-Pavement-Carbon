%% PSO-based calibration of CCI parameters
% Repository version: v1.0.2
%
% IMPORTANT:
% The manuscript-scale calibration requires the calibration workbooks and the
% corresponding runway-profile set. Those data are not bundled when they are
% too large or access-restricted. This script performs a strict preflight check
% and will NOT fabricate or silently replace missing calibration inputs.
%
% Required local files for a full rerun:
%   data/calibration/Energy_Dissipation_Results.xlsx
%   data/calibration/Parameter_Ranges.xlsx
%   data/calibration/Aircraft_Weights.xlsx
%   data/roughness_profiles/roughnessresult_1.mat ... roughnessresult_10.mat
%   code/calculate_CCI.m
%
% This file documents the original optimization workflow and is intended to be
% paired with locally authorized data for a full calibration rerun.

close all; clc; clear;

this_file = mfilename('fullpath');
code_dir = fileparts(this_file);
repo_root = fileparts(code_dir);
data_dir = fullfile(repo_root, 'data');
calib_dir = fullfile(data_dir, 'calibration');
rough_dir = fullfile(data_dir, 'roughness_profiles');
output_dir = fullfile(repo_root, 'outputs');
if ~exist(output_dir, 'dir'); mkdir(output_dir); end

energy_file = fullfile(calib_dir, 'Energy_Dissipation_Results.xlsx');
range_file = fullfile(calib_dir, 'Parameter_Ranges.xlsx');
weight_file = fullfile(calib_dir, 'Aircraft_Weights.xlsx');
helper_file = fullfile(code_dir, 'calculate_CCI.m');

required_files = {energy_file, range_file, weight_file, helper_file};
for k = 1:10
    required_files{end+1} = fullfile(rough_dir, sprintf('roughnessresult_%d.mat', k)); %#ok<SAGROW>
end

missing = required_files(cellfun(@(f) exist(f, 'file') ~= 2, required_files));
if ~isempty(missing)
    fprintf(2, '\nFull PSO calibration cannot start because the following local inputs are absent:\n');
    for k = 1:numel(missing)
        fprintf(2, '  %s\n', missing{k});
    end
    error(['No synthetic calibration result is generated. This safeguard prevents ', ...
           'demonstration data from being mistaken for manuscript calibration data.']);
end

addpath(code_dir);
fprintf('====== PSO calibration of standard-aircraft CCI parameters ======\n\n');

Energy_data = readmatrix(energy_file, 'Sheet', 'Eca_total', 'Range', 'B2:K21');
[n_aircraft, n_runways] = size(Energy_data);
runway_number = 1:n_runways;

param_range = readmatrix(range_file, 'Sheet', 'Sheet1', 'Range', 'B2:Q3');
param_min = param_range(1,:);
param_max = param_range(2,:);
param_names = {'ms','mf','mr','ml','ksf','ksr','ksl','ktf','ktr','ktl','csf','csr','csl','ctf','ctr','ctl'};
n_params = numel(param_names);

weight_table = readtable(weight_file, 'VariableNamingRule', 'preserve');
if width(weight_table) < 2
    error('Aircraft_Weights.xlsx must contain the aircraft label and weight in the first two columns.');
end
aircraft_weights = weight_table{1:n_aircraft,2};
aircraft_weights = aircraft_weights(:) / sum(aircraft_weights);

Energy_norm = zeros(n_aircraft, n_runways);
for i = 1:n_aircraft
    e_min = min(Energy_data(i,:));
    e_max = max(Energy_data(i,:));
    Energy_norm(i,:) = (Energy_data(i,:) - e_min) / (e_max - e_min + 1e-10);
end

% Reproducible optimizer seed
rng(20260922, 'twister');
n_particles = 100;
max_iter = 100;
w = 0.9; w_min = 0.4; c1 = 2.0; c2 = 2.0;

positions = param_min + rand(n_particles,n_params).*(param_max-param_min);
v_max = (param_max-param_min)*0.2;
velocities = -v_max + rand(n_particles,n_params).*(2*v_max);
pbest_positions = positions;
pbest_fitness = inf(n_particles,1);
gbest_position = zeros(1,n_params);
gbest_fitness = inf;
gbest_corr_weighted_mean = 0;
gbest_corr_min = 0;
gbest_corr_list = zeros(n_aircraft,1);
fitness_history = zeros(max_iter,1);
corr_weighted_mean_history = zeros(max_iter,1);
corr_min_history = zeros(max_iter,1);

fprintf('Aircraft types: %d; runway profiles: %d\n', n_aircraft, n_runways);
fprintf('Starting PSO...\n');

for iter = 1:max_iter
    t_iter = tic;
    w_current = w - (w-w_min)*iter/max_iter;

    for p = 1:n_particles
        params = positions(p,:);
        CCI_vector = zeros(1,n_runways);
        for runway_idx = 1:n_runways
            mat_filename = fullfile(rough_dir, sprintf('roughnessresult_%d.mat', runway_number(runway_idx)));
            CCI_vector(runway_idx) = calculate_CCI(params, mat_filename);
        end

        cci_range = max(CCI_vector) - min(CCI_vector);
        if cci_range < 1e-6 || std(CCI_vector) < 1e-8 || any(~isfinite(CCI_vector))
            fitness = 10;
            corr_weighted_mean = 0;
            corr_min_val = -1;
            corr_list = -ones(n_aircraft,1);
        else
            CCI_norm = (CCI_vector-min(CCI_vector))/cci_range;
            corr_list = zeros(n_aircraft,1);
            for i = 1:n_aircraft
                if std(Energy_norm(i,:)) < 1e-10
                    corr_list(i) = 0;
                else
                    R = corrcoef(CCI_norm, Energy_norm(i,:));
                    if all(isfinite(R(:))); corr_list(i) = R(1,2); else; corr_list(i) = 0; end
                end
            end
            corr_weighted_mean = sum(corr_list.*aircraft_weights);
            corr_min_val = min(corr_list);
            fitness = 0.7*(1-corr_weighted_mean) + 0.3*(1-corr_min_val);
        end

        if fitness < pbest_fitness(p)
            pbest_fitness(p) = fitness;
            pbest_positions(p,:) = positions(p,:);
        end
        if fitness < gbest_fitness
            gbest_fitness = fitness;
            gbest_position = positions(p,:);
            gbest_corr_weighted_mean = corr_weighted_mean;
            gbest_corr_min = corr_min_val;
            gbest_corr_list = corr_list;
        end
    end

    fitness_history(iter) = gbest_fitness;
    corr_weighted_mean_history(iter) = gbest_corr_weighted_mean;
    corr_min_history(iter) = gbest_corr_min;

    for p = 1:n_particles
        r1 = rand(1,n_params); r2 = rand(1,n_params);
        velocities(p,:) = w_current*velocities(p,:) ...
            + c1*r1.*(pbest_positions(p,:)-positions(p,:)) ...
            + c2*r2.*(gbest_position-positions(p,:));
        velocities(p,:) = max(-v_max, min(v_max, velocities(p,:)));
        positions(p,:) = positions(p,:) + velocities(p,:);
        below = positions(p,:) < param_min;
        above = positions(p,:) > param_max;
        positions(p,:) = max(param_min, min(param_max, positions(p,:)));
        velocities(p, below | above) = -0.5*velocities(p, below | above);
    end

    if mod(iter,10)==0 || iter==1
        fprintf('Iter %3d: fitness=%.4f, corr_weighted=%.4f, corr_min=%.4f, %.1fs\n', ...
            iter, gbest_fitness, gbest_corr_weighted_mean, gbest_corr_min, toc(t_iter));
    end
end

result_table = table(string(param_names(:)), gbest_position(:), ...
    'VariableNames', {'Parameter','OptimalValue'});
writetable(result_table, fullfile(output_dir, 'pso_optimal_parameters.csv'));
save(fullfile(output_dir, 'pso_calibration_results.mat'), ...
    'gbest_position','gbest_fitness','gbest_corr_weighted_mean','gbest_corr_min', ...
    'gbest_corr_list','fitness_history','corr_weighted_mean_history','corr_min_history');

fig = figure('Visible','off');
tiledlayout(1,3);
nexttile; plot(1:max_iter, fitness_history, 'LineWidth', 1.5); xlabel('Iteration'); ylabel('Fitness'); grid on;
nexttile; plot(1:max_iter, corr_weighted_mean_history, 'LineWidth', 1.5); xlabel('Iteration'); ylabel('Weighted mean correlation'); grid on;
nexttile; plot(1:max_iter, corr_min_history, 'LineWidth', 1.5); xlabel('Iteration'); ylabel('Minimum correlation'); grid on;
exportgraphics(fig, fullfile(output_dir, 'PSO_convergence.png'), 'Resolution', 300);
close(fig);

fprintf('PSO calibration completed. Outputs written to %s\n', output_dir);
