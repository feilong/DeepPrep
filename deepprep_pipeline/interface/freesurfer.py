from nipype.interfaces.base import BaseInterface, \
    BaseInterfaceInputSpec, traits, File, TraitedSpec, Directory, Str, traits_extension
from nipype import Node, Workflow
from run import run_cmd_with_timing, parse_args
import os
from pathlib import Path
import argparse


def get_freesurfer_threads(threads: int):
    if threads and threads > 1:
        fsthreads = f'-threads {threads} -itkthreads {threads}'
    else:
        fsthreads = ''
    return fsthreads


class BrainmaskInputSpec(BaseInterfaceInputSpec):
    subject_dir = Directory(exists=True, desc="subject dir", mandatory=True)
    subject_id = Str(desc="subject id", mandatory=True)
    need_t1 = traits.BaseCBool(desc='bool', mandatory=True)
    nu_file = File(exists=True, desc="nu file", mandatory=True)
    mask_file = File(exists=True, desc="mask file", mandatory=True)

    T1_file = File(exists=False, desc="T1 file", mandatory=True)
    brainmask_file = File(exists=False, desc="brainmask file", mandatory=True)
    norm_file = File(exists=False, desc="norm file", mandatory=True)


class BrainmaskOutputSpec(TraitedSpec):
    brainmask_file = File(exists=True, desc="brainmask file")
    norm_file = File(exists=True, desc="norm file")
    T1_file = File(exists=False, desc="T1 file")


class Brainmask(BaseInterface):
    input_spec = BrainmaskInputSpec
    output_spec = BrainmaskOutputSpec

    time = 74 / 60  # 运行时间：分钟
    cpu = 1  # 最大cpu占用：个
    gpu = 0  # 最大gpu占用：MB

    def _run_interface(self, runtime):
        # create norm by masking nu 0.7s
        need_t1 = self.inputs.need_t1
        cmd = f'mri_mask {self.inputs.nu_file} {self.inputs.mask_file} {self.inputs.norm_file}'
        run_cmd_with_timing(cmd)

        if need_t1:  # T1.mgz 相比 orig.mgz 更平滑，对比度更高
            # create T1.mgz from nu 96.9s
            cmd = f'mri_normalize -g 1 -mprage {self.inputs.nu_file} {self.inputs.T1_file}'
            run_cmd_with_timing(cmd)

            # create brainmask by masking T1
            cmd = f'mri_mask {self.inputs.T1_file} {self.inputs.mask_file} {self.inputs.brainmask_file}'
            run_cmd_with_timing(cmd)
        else:
            cmd = f'cp {self.inputs.norm_file} {self.inputs.brainmask_file}'
            run_cmd_with_timing(cmd)

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["brainmask_file"] = self.inputs.brainmask_file
        outputs["norm_file"] = self.inputs.norm_file
        outputs["T1_file"] = self.inputs.T1_file

        return outputs


class OrigAndRawavgInputSpec(BaseInterfaceInputSpec):
    t1w_files = traits.List(desc='t1w path or t1w paths', mandatory=True)
    subject_dir = Directory(exists=True, desc='subject dir path', mandatory=True)
    subject_id = Str(desc='subject id', mandatory=True)
    threads = traits.Int(desc='threads')


class OrigAndRawavgOutputSpec(TraitedSpec):
    orig_file = File(exists=True, desc='orig.mgz')
    rawavg_file = File(exists=True, desc='rawavg.mgz')


class OrigAndRawavg(BaseInterface):
    input_spec = OrigAndRawavgInputSpec
    output_spec = OrigAndRawavgOutputSpec

    def __init__(self):
        super(OrigAndRawavg, self).__init__()

    def _run_interface(self, runtime):
        threads = self.inputs.threads if self.inputs.threads else 0
        fsthreads = get_freesurfer_threads(threads)

        files = ' -i '.join(self.inputs.t1w_files)
        cmd = f"recon-all -subject {self.inputs.subject_id} -i {files} -motioncor {fsthreads}"
        run_cmd_with_timing(cmd)
        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["orig_file"] = Path(f"{self.inputs.subject_dir}/{self.inputs.subject_id}/mri/orig.mgz")
        outputs['rawavg_file'] = Path(f"{self.inputs.subject_dir}/{self.inputs.subject_id}/mri/rawavg.mgz")
        return outputs


class FilledInputSpec(BaseInterfaceInputSpec):
    aseg_auto_file = File(exists=True, desc='mri/aseg.auto.mgz', mandatory=True)
    norm_file = File(exists=True, desc='mri/norm.mgz', mandatory=True)
    brainmask_file = File(exists=True, desc='mri/brainmask.mgz', mandatory=True)
    talairach_file = File(exists=True, desc='mri/transforms/talairach.lta')
    subject_dir = Directory(exists=True, desc='subject dir path', mandatory=True)
    subject_id = Str(desc='subject id', mandatory=True)
    threads = traits.Int(desc='threads')


class FilledOutputSpec(TraitedSpec):
    aseg_presurf_file = File(exists=True, desc='mri/aseg.presurf.mgz')
    brain_file = File(exists=True, desc='mri/brain.mgz')
    brain_finalsurfs_file = File(exists=True, desc='mri/brain.finalsurfs.mgz')
    wm_file = File(exists=True, desc='mri/wm.mgz')


class Filled(BaseInterface):
    input_spec = OrigAndRawavgInputSpec
    output_spec = OrigAndRawavgOutputSpec

    def __init__(self):
        super(Filled, self).__init__()

    def _run_interface(self, runtime):
        threads = self.inputs.threads if self.inputs.threads else 0
        fsthreads = get_freesurfer_threads(threads)

        files = ' -i '.join(self.inputs.t1w_files)
        cmd = f"recon-all -subject {self.inputs.subject_id} -i {files} -motioncor {fsthreads}"
        run_cmd_with_timing(cmd)
        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["orig_file"] = Path(f"{self.inputs.subject_dir}/{self.inputs.subject_id}/mri/orig.mgz")
        outputs['rawavg_file'] = Path(f"{self.inputs.subject_dir}/{self.inputs.subject_id}/mri/rawavg.mgz")
        return outputs


class WhitePreaparcInputSpec(BaseInterfaceInputSpec):
    fswhitepreaparc = traits.Bool(desc="True: mris_make_surfaces; \
    False: recon-all -autodetgwstats -white-preaparc -cortex-label", mandatory=True)
    subject = traits.Str(desc="sub-xxx", mandatory=True)
    hemi = traits.Str(desc="?h", mandatory=True)

    # input files of <mris_make_surfaces>
    aseg_presurf = File(exists=True, desc="mri/aseg.presurf.mgz")
    brain_finalsurfs = File(exists=True, desc="mri/brain.finalsurfs.mgz")
    wm_file = File(exists=True, desc="mri/wm.mgz")
    filled_file = File(exists=True, desc="mri/filled.mgz")
    hemi_orig = File(exists=True, desc="surf/?h.orig")

    # input files of <recon-all -autodetgwstats>
    hemi_orig_premesh = File(exists=True, desc="surf/?h.orig.premesh")

    # input files of <recon-all -white-paraparc>
    autodet_gw_stats_hemi_dat = File(exists=True, desc="surf/autodet.gw.stats.?h.dat")

    # input files of <recon-all -cortex-label>
    hemi_white_preaparc = File(exists=True, desc="surf/?h.white.preaparc")


class WhitePreaparcOutputSpec(TraitedSpec):
    # output files of mris_make_surfaces
    hemi_white_preaparc = File(exists=True, desc="surf/?h.white.preaparc")
    hemi_curv = File(exists=True, desc="surf/?h.curv")
    hemi_area = File(exists=True, desc="surf/?h.area")
    hemi_cortex_label = File(exists=True, desc="label/?h.cortex.label")


class WhitePreaparc(BaseInterface):
    input_spec = WhitePreaparcInputSpec
    output_spec = WhitePreaparcOutputSpec

    def __init__(self, output_dir: Path, threads: int):
        super(WhitePreaparc, self).__init__()
        self.output_dir = output_dir
        self.threads = threads
        self.fsthreads = get_freesurfer_threads(threads)


    def _run_interface(self, runtime):
        if not traits_extension.isdefined(self.inputs.brain_finalsurfs):
            self.inputs.brain_finalsurfs = self.output_dir / f"{self.inputs.subject}" / "mri/brain.finalsurfs.mgz"
        if not traits_extension.isdefined(self.inputs.wm_file):
            self.inputs.wm_file = self.output_dir / f"{self.inputs.subject}" / "mri/wm.mgz"
        print("-------------")
        print(f"self.inputs.brain_finalsurfs {self.inputs.brain_finalsurfs}")
        print(f"self.inputs.wm_file {self.inputs.wm_file}")
        print("--------------")

        if self.inputs.fswhitepreaparc:
            time = 130 / 60
            cpu = 1.25
            gpu = 0

            if not traits_extension.isdefined(self.inputs.aseg_presurf):
                self.inputs.aseg_presurf = self.output_dir / f"{self.inputs.subject}" / "mri/aseg.presurf.mgz"
            if not traits_extension.isdefined(self.inputs.filled_file):
                self.inputs.filled_file = self.output_dir / f"{self.inputs.subject}" / "mri/filled.mgz"
            if not traits_extension.isdefined(self.inputs.hemi_orig):
                self.inputs.hemi_orig = self.output_dir / f"{self.inputs.subject}" / "surf" / f"{self.inputs.hemi}.orig"
            print("*"*10)
            print(f"self.inputs.aseg_presurf {self.inputs.aseg_presurf}")
            print(f"self.inputs.filled_file {self.inputs.filled_file}")
            print(f"self.inputs.hemi_orig {self.inputs.hemi_orig}")
            print("*"*10)

            cmd = f'mris_make_surfaces -aseg aseg.presurf -white white.preaparc -whiteonly -noaparc -mgz ' \
                  f'-T1 brain.finalsurfs {self.inputs.subject} {self.inputs.hemi} threads {self.threads}'
            run_cmd_with_timing(cmd)
        else:
            # time = ? / 60
            # cpu = ?
            # gpu = 0

            if not traits_extension.isdefined(self.inputs.hemi_orig_premesh):
                self.inputs.hemi_orig_premesh = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.orig.premesh"

            cmd = f'recon-all -subject {self.inputs.subject} -hemi {self.inputs.hemi} -autodetgwstats -white-preaparc -cortex-label ' \
                  f'-no-isrunning {self.fsthreads}'
            run_cmd_with_timing(cmd)

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["hemi_white_preaparc"] = self.inputs.hemi_white_preaparc
        outputs["hemi_curv"] = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.curv"
        outputs["hemi_area"] = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.area"
        outputs["hemi_cortex_label"] = self.output_dir / f"{self.inputs.subject}" / f"label/{self.inputs.hemi}.cortex.label"
        return outputs


class Inflated_SphereThresholdInputSpec(BaseInterfaceInputSpec):
    hemi=traits.String(mandatory=True, desc='hemi')
    fsthreads=traits.String(mandatory=True, desc='fsthreads')
    subject=traits.String(mandatory=True, desc='recon')
    white_preaparc_file = File(exists=True, mandatory=True, desc='surf/?h.white.preaparc')
    smoothwm_file = File(mandatory=True, desc='surf/?h.smoothwm')
    inflated_file = File(mandatory=True, desc='surf/?h.inflated')  # Do not set exists=True !!
    sulc_file = File(mandatory=True, desc="surf/?h.sulc")


class Inflated_SphereThresholdOutputSpec(TraitedSpec):
    smoothwm_file = File(exists=True, mandatory=True, desc='surf/?h.smoothwm')
    inflated_file = File(exists=True, mandatory=True, desc='surf/?h.inflated')  # Do not set exists=True !!
    sulc_file = File(exists=True, mandatory=True, desc="surf/?h.sulc")


class Inflated_Sphere(BaseInterface):
    input_spec = Inflated_SphereThresholdInputSpec
    output_spec = Inflated_SphereThresholdOutputSpec

    # time = 634 / 60  # 运行时间：分钟
    # cpu = 20  # 最大cpu占用：个
    # gpu = 0  # 最大gpu占用：MB

    def _run_interface(self, runtime):
        # create nicer inflated surface from topo fixed (not needed, just later for visualization)
        cmd = f"recon-all -subject {self.inputs.subject} -hemi {self.inputs.hemi} -smooth2 -no-isrunning {self.inputs.fsthreads}"
        run_cmd_with_timing(cmd)

        cmd = f"recon-all -subject {self.inputs.subject} -hemi {self.inputs.hemi} -Inflated_Sphere -no-isrunning {self.inputs.fsthreads}"
        run_cmd_with_timing(cmd)

        cmd = f"recon-all -subject {self.inputs.subject} -hemi {self.inputs.hemi} -sphere -no-isrunning {self.inputs.fsthreads}"
        run_cmd_with_timing(cmd)
        return runtime

        def _list_outputs(self):
            outputs = self._outputs().get()
            outputs['smoothwm_file'] = self.inputs.smoothwm_file
            outputs['inflated_file'] = self.inputs.inflated_file
            outputs['sulc_file'] = self.inputs.sulc_file
            return outputs



class WhitePialThicknessInputSpec(BaseInterfaceInputSpec):
    fswhitepial = traits.Bool(desc="True: recon-all -white & -pial; False: mris_place_surface", mandatory=True)
    subject = traits.Str(desc="sub-xxx", mandatory=True)
    hemi = traits.Str(desc="?h", mandatory=True)

    autodet_gw_stats_hemi_dat = File(exists=True, desc="surf/autodet.gw.stats.?h.dat")
    aseg_presurf = File(exists=True, desc="mri/aseg.presurf.mgz")
    wm_file = File(exists=True, desc="mri/wm.mgz")
    brain_finalsurfs = File(exists=True, desc="mri/brain.finalsurfs.mgz")
    hemi_white_preaparc = File(exists=True, desc="surf/?h.white.preaparc")
    hemi_white = File(exists=True, desc="surf/?h.white")
    hemi_cortex_label = File(exists=True, desc="label/?h.cortex.label")
    hemi_aparc_DKTatlas_mapped_annot = File(exists=True, desc="label/?h.aparc.DKTatlas.mapped.annot")

    hemi_pial_t1 = File(exists=True, desc="surf/?h.pial.T1")
    hemi_cortexhipamyg_label = File(exists=True, desc="label/?h.cortex+hipamyg.label")
    hemi_pial = File(exists=True, desc="surf/?h.pial")

    hemi_curv = File(exists=True, desc="surf/?h.curv")
    hemi_area = File(exists=True, desc="surf/?h.area")
    hemi_curv_pial = File(exists=True, desc="surf/?h.curv.pial")
    hemi_area_pial = File(exists=True, desc="surf/?h.area.pial")
    hemi_thickness = File(exists=True, desc="surf/?h.thickness")


class WhitePialThicknessOutputSpec(TraitedSpec):
    hemi_white = File(exists=True, desc="surf/?h.white")
    hemi_pial_t1 = File(exists=True, desc="surf/?h.pial.T1")

    hemi_pial = File(exists=True, desc="surf/?h.pial")

    hemi_curv = File(exists=True, desc="surf/?h.curv")
    hemi_area = File(exists=True, desc="surf/?h.area")
    hemi_curv_pial = File(exists=True, desc="surf/?h.curv.pial")
    hemi_area_pial = File(exists=True, desc="surf/?h.area.pial")
    hemi_thickness = File(exists=True, desc="surf/?h.thickness")



class WhitePialThickness(BaseInterface):
    input_spec = WhitePialThicknessInputSpec
    output_spec = WhitePialThicknessOutputSpec

    def __init__(self, output_dir: Path, threads: int):
        super(WhitePialThickness, self).__init__()
        self.output_dir = output_dir
        self.threads = threads
        self.fsthreads = get_freesurfer_threads(threads)
        # self.sub_mri_dir = self.output_dir / self.inputs.subject / "mri"

    def _run_interface(self, runtime):
        if self.inputs.fswhitepial:
            # must run surfreg first
            # 20-25 min for traditional surface segmentation (each hemi)
            # this creates aparc and creates pial using aparc, also computes jacobian
            time = (135 + 120) / 60
            # cpu =
            # gpu =

            cmd = f"recon-all -subject {self.inputs.subject} -hemi {self.inputs.hemi} -white " \
                  f"-no-isrunning {self.fsthreads}"
            run_cmd_with_timing(cmd)
            cmd = f"recon-all -subject {self.inputs.subject} -hemi {self.inputs.hemi} -pial " \
                  f"-no-isrunning {self.fsthreads}"
            run_cmd_with_timing(cmd)
        else:
            # 4 min compute white :
            if not traits_extension.isdefined(self.inputs.autodet_gw_stats_hemi_dat):
                self.inputs.autodet_gw_stats_hemi_dat = self.output_dir / f"{self.inputs.subject}" / f"surf/autodet.gw.stats.{self.inputs.hemi}.dat"
            if not traits_extension.isdefined(self.inputs.aseg_presurf):
                self.inputs.aseg_presurf = self.output_dir / f"{self.inputs.subject}" / "mri/aseg.presurf.mgz"
            if not traits_extension.isdefined(self.inputs.wm_file):
                self.inputs.wm_file = self.output_dir / f"{self.inputs.subject}" / "mri/wm.mgz"
            if not traits_extension.isdefined(self.inputs.brain_finalsurfs):
                self.inputs.brain_finalsurfs = self.output_dir / f"{self.inputs.subject}" / "mri/brain.finalsurfs.mgz"
            if not traits_extension.isdefined(self.inputs.hemi_white_preaparc):
                self.inputs.hemi_white_preaparc = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.white.preaparc"
            if not traits_extension.isdefined(self.inputs.hemi_white):
                self.inputs.hemi_white = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.white"
            if not traits_extension.isdefined(self.inputs.hemi_cortex_label):
                self.inputs.hemi_cortex_label = self.output_dir / f"{self.inputs.subject}" / f"label/{self.inputs.hemi}.cortex.label"
            if not traits_extension.isdefined(self.inputs.hemi_aparc_DKTatlas_mapped_annot):
                self.inputs.hemi_aparc_DKTatlas_mapped_annot = self.output_dir / f"{self.inputs.subject}" / f"label/{self.inputs.hemi}.aparc.DKTatlas.mapped.annot"

            if not traits_extension.isdefined(self.inputs.hemi_pial_t1):
                self.inputs.hemi_pial_t1 = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.pial.T1"
            if not traits_extension.isdefined(self.inputs.hemi_cortexhipamyg_label):
                self.inputs.hemi_cortexhipamyg_label = self.output_dir / f"{self.inputs.subject}" / f"label/{self.inputs.hemi}.cortex+hipamyg.label"
            if not traits_extension.isdefined(self.inputs.hemi_pial):
                self.inputs.hemi_pial = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.pial"

            if not traits_extension.isdefined(self.inputs.hemi_curv):
                self.inputs.hemi_curv = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.curv"
            if not traits_extension.isdefined(self.inputs.hemi_area):
                self.inputs.hemi_area = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.area"
            if not traits_extension.isdefined(self.inputs.hemi_curv_pial):
                self.inputs.hemi_curv_pial = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.curv.pial"
            if not traits_extension.isdefined(self.inputs.hemi_area_pial):
                self.inputs.hemi_area_pial = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.area.pial"
            if not traits_extension.isdefined(self.inputs.hemi_thickness):
                self.inputs.hemi_thickness = self.output_dir / f"{self.inputs.subject}" / f"surf/{self.inputs.hemi}.thickness"

            # time =
            # cpu =
            # gpu =
            cddir = f'cd {self.output_dir / self.inputs.subject / "mri"} &&'
            cmd = f"{cddir} mris_place_surface --adgws-in {self.inputs.autodet_gw_stats_hemi_dat} " \
                  f"--seg {self.inputs.aseg_presurf} --wm {self.inputs.wm_file} --invol {self.inputs.brain_finalsurfs} --{self.inputs.hemi} " \
                  f"--i {self.inputs.hemi_white_preaparc} --o {self.inputs.hemi_white} --white --nsmooth 0 " \
                  f"--rip-label {self.inputs.hemi_cortex_label} --rip-bg --rip-surf {self.inputs.hemi_white_preaparc} " \
                  f"--aparc {self.inputs.hemi_aparc_DKTatlas_mapped_annot}"
            run_cmd_with_timing(cmd)
            # 4 min compute pial :
            cmd = f"{cddir} mris_place_surface --adgws-in {self.inputs.autodet_gw_stats_hemi_dat} --seg {self.inputs.aseg_presurf} " \
                  f"--wm {self.inputs.wm_file} --invol {self.inputs.brain_finalsurfs} --{self.inputs.hemi} --i {self.inputs.hemi_white} " \
                  f"--o {self.inputs.hemi_pial_t1} --pial --nsmooth 0 --rip-label {self.inputs.hemi_cortexhipamyg_label} " \
                  f"--pin-medial-wall {self.inputs.hemi_cortex_label} --aparc {self.inputs.hemi_aparc_DKTatlas_mapped_annot} " \
                  f"--repulse-surf {self.inputs.hemi_white} --white-surf {self.inputs.hemi_white}"
            run_cmd_with_timing(cmd)

            # Here insert DoT2Pial  later --> if T2pial is not run, need to softlink pial.T1 to pial!

            cmd = f"cp {self.inputs.hemi_pial_t1} {self.inputs.hemi_pial}"
            run_cmd_with_timing(cmd)

            # these are run automatically in fs7* recon-all and
            # cannot be called directly without -pial flag (or other t2 flags)
            cmd = f"{cddir} mris_place_surface --curv-map {self.inputs.hemi_white} 2 10 {self.inputs.hemi_curv}"
            run_cmd_with_timing(cmd)
            cmd = f"{cddir} mris_place_surface --area-map {self.inputs.hemi_white} {self.inputs.hemi_area}"
            run_cmd_with_timing(cmd)
            cmd = f"{cddir} mris_place_surface --curv-map {self.inputs.hemi_pial} 2 10 {self.inputs.hemi_curv_pial}"
            run_cmd_with_timing(cmd)
            cmd = f"{cddir} mris_place_surface --area-map {self.inputs.hemi_pial} {self.inputs.hemi_area_pial}"
            run_cmd_with_timing(cmd)
            cmd = f"{cddir} mris_place_surface --thickness {self.inputs.hemi_white} {self.inputs.hemi_pial} " \
                  f"20 5 {self.inputs.hemi_thickness}"
            run_cmd_with_timing(cmd)

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["hemi_white"] = self.inputs.hemi_white
        outputs["hemi_pial_t1"] = self.inputs.hemi_pial_t1
        outputs["hemi_pial"] = self.inputs.hemi_pial
        outputs["hemi_curv"] = self.inputs.hemi_curv
        outputs["hemi_area"] = self.inputs.hemi_area
        outputs["hemi_curv_pial"] = self.inputs.hemi_curv_pial
        outputs["hemi_area_pial"] = self.inputs.hemi_area_pial
        outputs["hemi_thickness"] = self.inputs.hemi_thickness

        return outputs