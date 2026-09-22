%% CCI calculation workflow
% Repository version: v1.0.2
% By default this script runs a lightweight demonstration using the bundled
% data/example_roughness_profile.mat. The large/full runway-profile set is NOT
% required for the demo.
%
% To run the manuscript-scale batch, change RUN_MODE to "batch" and place the
% required roughness files under data/roughness_profiles/ using the naming
% convention roughnessresult_2.20.mat ... roughnessresult_2.80.mat.

clc; clear; close all;
tic;

%% Repository-relative paths
this_file = mfilename('fullpath');
code_dir = fileparts(this_file);
repo_root = fileparts(code_dir);
data_dir = fullfile(repo_root, 'data');
output_dir = fullfile(repo_root, 'outputs');
if ~exist(output_dir, 'dir'); mkdir(output_dir); end

%% Run mode
RUN_MODE = "demo";  % "demo" or "batch"

if RUN_MODE == "demo"
    profile_files = {fullfile(data_dir, 'example_roughness_profile.mat')};
    profile_labels = {"example"};
    roughness_levels = 1.0;  % label only; not a manuscript roughness level
else
    roughness_levels = 2.20:0.01:2.80;
    profile_files = cell(size(roughness_levels));
    profile_labels = cell(size(roughness_levels));
    for k = 1:numel(roughness_levels)
        profile_labels{k} = sprintf('%.2f', roughness_levels(k));
        profile_files{k} = fullfile(data_dir, 'roughness_profiles', ...
            sprintf('roughnessresult_%.2f.mat', roughness_levels(k)));
    end
end

% Explicitly fail for missing requested data. Do not silently substitute a
% synthetic runway profile in a manuscript-reproduction run.
missing_mask = ~cellfun(@(f) exist(f, 'file') == 2, profile_files);
if any(missing_mask)
    fprintf(2, '\nMissing roughness input(s):\n');
    missing_files = profile_files(missing_mask);
    for k = 1:numel(missing_files)
        fprintf(2, '  %s\n', missing_files{k});
    end
    error(['Required roughness files are not bundled. Use RUN_MODE="demo" ', ...
           'for the lightweight example, or provide the full data locally.']);
end

%% Operating condition
ve_list = 210/3.6;
v_kmh_all = ve_list * 3.6;
n_ve = numel(ve_list);
n_rough = numel(profile_files);

results = struct( ...
    'roughness_level', roughness_levels, ...
    'v_kmh', repmat(v_kmh_all, n_rough, 1), ...
    'Eca_total', zeros(n_rough, n_ve), ...
    'CCI1', zeros(n_rough, n_ve), ...
    'x_static_f', zeros(n_rough, n_ve), ...
    'x_static_r', zeros(n_rough, n_ve), ...
    'lift_ratio', zeros(n_rough, n_ve), ...
    'ksf', zeros(n_rough, n_ve), ...
    'ksr', zeros(n_rough, n_ve));

%% Model parameters
z0 = 620;
lc = 15.6;
L = 1120;
dt = 8e-5;
Le = L - z0;
g = 9.81;
max_nt = 1e5;

rho_a = 1.298;
s_w = 62.29 * 2;
ms = 32217.8741; Ix = 3394953; Iy = 1866711;
mf = 361.2187; mr = 1449.9961; ml = 1449.9961;
lf = 13.4; lm = 0.9; br = 3.4; bl = 3.4;
csf_base = 36531.5017;
csr_base = 159044.1801;
csl_base = 159044.1801;
ctf_base = 3950.0025;
ctr_base = 4016.0189;
ctl_base = 4016.0189;

ksf_min = 4.0e4; ksf_max = 2.0e6;
ksr_min = 7.0e5; ksr_max = 2.0e7;
ktf_k0 = 546250.0000; ktf_k1 = 3.2e3;
ktr_k0 = 2585210.8928; ktr_k1 = 3.2e3;
F_tire_min = 500;

for r_idx = 1:n_rough
    label = profile_labels{r_idx};
    filename = profile_files{r_idx};
    fprintf('\n============================================\n');
    fprintf('Profile: %s\n', label);
    fprintf('File: %s\n', filename);
    fprintf('============================================\n');

    shice = load(filename);
    if ~isfield(shice, 'roughness_data')
        error('MAT file %s does not contain variable roughness_data.', filename);
    end
    Z3D = shice.roughness_data;
    if size(Z3D, 2) > 1; Z3D = Z3D(:, 1); end
    Z2D = Z3D(:)';
    x_Z2D = 0:0.25:0.25*(numel(Z2D)-1);

    % Filtering fallback keeps the demo runnable without Signal Processing
    % Toolbox. The manuscript implementation used the FIR/filtfilt branch.
    if exist('fir1', 'file') == 2 && exist('filtfilt', 'file') == 2
        b_low = fir1(8, 0.1, 'low');
        Z2D_filtered = filtfilt(b_low, 1, Z2D);
    else
        warning('fir1/filtfilt unavailable; using movmean(9) for demo filtering.');
        Z2D_filtered = movmean(Z2D, 9);
    end

    % MATLAB's built-in spline removes the dependency on csape.
    yr_ce = spline(x_Z2D, Z2D_filtered);

    if max(x_Z2D) < L
        error('Profile length %.2f m is shorter than required model length %.2f m.', max(x_Z2D), L);
    end

    for i = 1:n_ve
        ve = ve_list(i);
        v_kmh = v_kmh_all(i);
        tm = Le / ve;
        nt = min(floor(tm / dt), max_nt);
        T = dt*(0:nt);

        if v_kmh < 120
            c_l = 0.61;
        elseif v_kmh < 200
            c_l = 1.36;
        else
            c_l = 1.36;
        end

        Fl = 0.5 * rho_a * s_w * c_l * ve^2;
        lift_ratio = min((Fl/(ms*g))*100, 100);
        Fl = min(Fl, ms*g);
        F_sprung_net = max(ms*g - Fl, 0);

        F_spring_f = F_sprung_net * (lm/(lf+lm));
        F_spring_r = F_sprung_net * (lf/(lf+lm))/2;

        roots_f = roots([0.0005, -0.0292, 16.055, -(7963.7 + F_spring_f)]);
        valid_roots_f = roots_f(abs(imag(roots_f)) < 1e-10 & real(roots_f) >= 0 & real(roots_f) < 1000);
        if isempty(valid_roots_f); x_static_f_mm = 0; else; x_static_f_mm = min(real(valid_roots_f)); end

        roots_r = roots([0.0109, -1.183, 186.94, -(97898 + F_spring_r)]);
        valid_roots_r = roots_r(abs(imag(roots_r)) < 1e-10 & real(roots_r) >= 0 & real(roots_r) < 1000);
        if isempty(valid_roots_r); x_static_r_mm = 0; else; x_static_r_mm = min(real(valid_roots_r)); end

        k_tan_f_Nmm = 3*0.0005*x_static_f_mm^2 - 2*0.0292*x_static_f_mm + 16.055;
        ksf = max(min(k_tan_f_Nmm*1000, ksf_max), ksf_min);
        k_tan_r_Nmm = 3*0.0109*x_static_r_mm^2 - 2*1.183*x_static_r_mm + 186.94;
        ksr = max(min(k_tan_r_Nmm*1000, ksr_max), ksr_min);
        ksl = ksr;

        csf = csf_base; csr = csr_base; csl = csl_base;
        ctf = ctf_base; ctr = ctr_base; ctl = ctl_base;

        F_tire_f_load = max((ms+mf+mr+ml)*g - Fl, F_tire_min) * (lm/(lf+lm));
        F_tire_r_load = max((ms+mf+mr+ml)*g - Fl, F_tire_min) * (lf/(lf+lm))/2;
        ktf = ktf_k0 + ktf_k1*sqrt(F_tire_f_load);
        ktr = ktr_k0 + ktr_k1*sqrt(F_tire_r_load);
        ktl = ktr;

        Ma = diag([ms, Ix, Iy, mf, mr, ml]);
        Ka = [
            ksf+ksl+ksr,          ksf*lf-ksl*lm-ksr*lm,       -ksl*bl+ksr*br,      -ksf,     -ksr,    -ksl;
            ksf*lf-ksl*lm-ksr*lm, ksf*lf^2+ksl*lm^2+ksr*lm^2, ksl*bl*lm-ksr*br*lm, -ksf*lf,  ksr*lm,  ksl*lm;
            -ksl*bl+ksr*br,       ksl*lm*bl-ksr*lm*br,        ksl*bl^2+ksr*br^2,     0,      -ksr*br, ksl*bl;
            -ksf,                 -ksf*lf,                     0,                    ksf+ktf,  0,       0;
            -ksr,                  ksr*lm,                    -ksr*br,               0,        ksr+ktr, 0;
            -ksl,                  ksl*lm,                     ksl*bl,               0,        0,       ksl+ktl];
        Ca = [
            csf+csl+csr,          csf*lf-csl*lm-csr*lm,       -csl*bl+csr*br,      -csf,     -csr,    -csl;
            csf*lf-csl*lm-csr*lm, csf*lf^2+csl*lm^2+csr*lm^2, csl*bl*lm-csr*br*lm, -csf*lf,  csr*lm,  csl*lm;
            -csl*bl+csr*br,       csl*lm*bl-csr*lm*br,        csl*bl^2+csr*br^2,     0,      -csr*br, csl*bl;
            -csf,                 -csf*lf,                     0,                    csf+ctf,  0,       0;
            -csr,                  csr*lm,                    -csr*br,               0,        csr+ctr, 0;
            -csl,                  csl*lm,                     csl*bl,               0,        0,       csl+ctl];

        z1 = z0 + T*ve; z2 = z1 - lc; z3 = z2;
        yr1 = ppval(yr_ce, z1); yr2 = ppval(yr_ce, z2); yr3 = ppval(yr_ce, z3);
        dyr1 = gradient(yr1)./gradient(T);
        dyr2 = gradient(yr2)./gradient(T);
        dyr3 = gradient(yr3)./gradient(T);

        N_air_dof = size(Ma,1);
        Ua = zeros(N_air_dof, nt+1); Va = zeros(N_air_dof, nt+1); Aa = zeros(N_air_dof, nt+1);
        Fa = zeros(N_air_dof, nt+1);
        Ua(:,1) = (Ka + 1e-6*eye(size(Ka))) \ [Fl-ms*g; 0; 0; -mf*g; -mr*g; -ml*g];

        gamma = 0.5; beta = 0.25;
        a0 = 1/(beta*dt^2); a1 = gamma/(beta*dt); a2 = 1/(beta*dt);
        a3 = 1/(2*beta)-1; a4 = gamma/beta-1; a5 = dt/2*(gamma/beta-2);
        a6 = dt*(1-gamma); a7 = gamma*dt;
        Ke = Ka + a0*Ma + a1*Ca;

        for j = 2:nt+1
            Fa(:,j) = [Fl-ms*g; 0; 0; ...
                ktf*yr1(j)+ctf*dyr1(j)-mf*g; ...
                ktr*yr2(j)+ctr*dyr2(j)-mr*g; ...
                ktl*yr3(j)+ctl*dyr3(j)-ml*g];
            Fe = Fa(:,j) + Ma*(a0*Ua(:,j-1)+a2*Va(:,j-1)+a3*Aa(:,j-1)) ...
                + Ca*(a1*Ua(:,j-1)+a4*Va(:,j-1)+a5*Aa(:,j-1));
            Ua1 = Ke \ Fe;
            Aa1 = a0*(Ua1-Ua(:,j-1)) - a2*Va(:,j-1) - a3*Aa(:,j-1);
            Va1 = Va(:,j-1) + a6*Aa(:,j-1) + a7*Aa1;
            Ua(:,j) = Ua1; Va(:,j) = Va1; Aa(:,j) = Aa1;
        end

        v_s1 = Va(1,:) + lf*Va(2,:) - Va(4,:);
        v_s2 = Va(1,:) - lm*Va(2,:) + br*Va(3,:) - Va(5,:);
        v_s3 = Va(1,:) - lm*Va(2,:) - bl*Va(3,:) - Va(6,:);
        v_t1 = Va(4,:) - dyr1;
        v_t2 = Va(5,:) - dyr2;
        v_t3 = Va(6,:) - dyr3;

        Eca_total = csf*sum(v_s1.^2)*dt + csr*sum(v_s2.^2)*dt + csl*sum(v_s3.^2)*dt ...
            + ctf*sum(v_t1.^2)*dt + ctr*sum(v_t2.^2)*dt + ctl*sum(v_t3.^2)*dt;
        v_sum = sum(abs(v_s1)) + sum(abs(v_s2)) + sum(abs(v_s3)) ...
            + sum(abs(v_t1)) + sum(abs(v_t2)) + sum(abs(v_t3));
        CCI1 = 100*(v_sum/6)*dt*ve/Le;

        results.Eca_total(r_idx,i) = Eca_total;
        results.CCI1(r_idx,i) = CCI1;
        results.x_static_f(r_idx,i) = x_static_f_mm;
        results.x_static_r(r_idx,i) = x_static_r_mm;
        results.lift_ratio(r_idx,i) = lift_ratio;
        results.ksf(r_idx,i) = ksf;
        results.ksr(r_idx,i) = ksr;

        fprintf('Eca_total = %.4e J (%.4f MJ), CCI1 = %.6f s^-1\n', ...
            Eca_total, Eca_total/1e6, CCI1);
    end
end

%% Save an explicit demo/batch result table
Profile = string(profile_labels(:));
RoughnessLabel = roughness_levels(:);
Speed_kmh = results.v_kmh(:,1);
Eca_total_J = results.Eca_total(:,1);
Eca_total_MJ = Eca_total_J/1e6;
CCI1_s_inv = results.CCI1(:,1);
Lift_ratio_pct = results.lift_ratio(:,1);
out_table = table(Profile, RoughnessLabel, Speed_kmh, Eca_total_J, Eca_total_MJ, CCI1_s_inv, Lift_ratio_pct);

if RUN_MODE == "demo"
    csv_out = fullfile(output_dir, 'cci_demo_results.csv');
    mat_out = fullfile(output_dir, 'cci_demo_results.mat');
else
    csv_out = fullfile(output_dir, 'cci_batch_results.csv');
    mat_out = fullfile(output_dir, 'cci_batch_results.mat');
end
writetable(out_table, csv_out);
save(mat_out, 'results', 'out_table', 'RUN_MODE');
fprintf('\nSaved: %s\nSaved: %s\n', csv_out, mat_out);
fprintf('Elapsed time: %.2f s\n', toc);
