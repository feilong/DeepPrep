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
    subjects_dir = Directory(exists=True, desc="subject dir", mandatory=True)
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
    subjects_dir = Directory(exists=True, desc='subject dir path', mandatory=True)
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
        outputs["orig_file"] = Path(f"{self.inputs.subjects_dir}/{self.inputs.subject_id}/mri/orig.mgz")
        outputs['rawavg_file'] = Path(f"{self.inputs.subjects_dir}/{self.inputs.subject_id}/mri/rawavg.mgz")
        return outputs


class FilledInputSpec(BaseInterfaceInputSpec):
    aseg_auto_file = File(exists=True, desc='mri/aseg.auto.mgz', mandatory=True)
    norm_file = File(exists=True, desc='mri/norm.mgz', mandatory=True)
    brainmask_file = File(exists=True, desc='mri/brainmask.mgz', mandatory=True)
    talairach_file = File(exists=True, desc='mri/transforms/talairach.lta')
    subjects_dir = Directory(exists=True, desc='subject dir path', mandatory=True)
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
        outputs["orig_file"] = Path(f"{self.inputs.subjects_dir}/{self.inputs.subject_id}/mri/orig.mgz")
        outputs['rawavg_file'] = Path(f"{self.inputs.subjects_dir}/{self.inputs.subject_id}/mri/rawavg.mgz")
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
            print("*" * 10)
            print(f"self.inputs.aseg_presurf {self.inputs.aseg_presurf}")
            print(f"self.inputs.filled_file {self.inputs.filled_file}")
            print(f"self.inputs.hemi_orig {self.inputs.hemi_orig}")
            print("*" * 10)

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
        outputs[
            "hemi_cortex_label"] = self.output_dir / f"{self.inputs.subject}" / f"label/{self.inputs.hemi}.cortex.label"
        return outputs




class InflatedSphereThresholdInputSpec(BaseInterfaceInputSpec):
    hemi = traits.String(mandatory=True, desc='hemi')
    subject = traits.String(mandatory=True, desc='recon')
    white_preaparc_file = File(exists=True, mandatory=True, desc='surf/?h.white.preaparc')
    smoothwm_file = File(mandatory=True, desc='surf/?h.smoothwm')
    inflated_file = File(mandatory=True, desc='surf/?h.inflated')  # Do not set exists=True !!
    sulc_file = File(mandatory=True, desc="surf/?h.sulc")
    threads = traits.Int(desc='threads')


class InflatedSphereThresholdOutputSpec(TraitedSpec):
    smoothwm_file = File(exists=True, mandatory=True, desc='surf/?h.smoothwm')
    inflated_file = File(exists=True, mandatory=True, desc='surf/?h.inflated')  # Do not set exists=True !!
    sulc_file = File(exists=True, mandatory=True, desc="surf/?h.sulc")


class InflatedSphere(BaseInterface):
    input_spec = InflatedSphereThresholdInputSpec
    output_spec = InflatedSphereThresholdOutputSpec

    time = 351 / 60  # 运行时间：分钟
    cpu = 5  # 最大cpu占用：个
    gpu = 0  # 最大gpu占用：MB

    def _run_interface(self, runtime):
        threads = self.inputs.threads if self.inputs.threads else 0
        fsthreads = get_freesurfer_threads(threads)
        # create nicer inflated surface from topo fixed (not needed, just later for visualization)
        cmd = f"recon-all -subject {self.inputs.subject} -hemi {self.inputs.hemi} -smooth2 -no-isrunning {fsthreads}"
        run_cmd_with_timing(cmd)

        cmd = f"recon-all -subject {self.inputs.subject} -hemi {self.inputs.hemi} -inflate2 -no-isrunning {fsthreads}"
        run_cmd_with_timing(cmd)

        cmd = f"recon-all -subject {self.inputs.subject} -hemi {self.inputs.hemi} -sphere -no-isrunning {fsthreads}"
        run_cmd_with_timing(cmd)
        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['smoothwm_file'] = self.inputs.smoothwm_file
        outputs['inflated_file'] = self.inputs.inflated_file
        outputs['sulc_file'] = self.inputs.sulc_file
        return outputs


class CurvstatsInputSpec(BaseInterfaceInputSpec):
    subject_dir = Directory(exists=True, desc="subject dir", mandatory=True)
    subject_id = Str(desc="subject id", mandatory=True)
    hemi = Str(desc="lh/rh", mandatory=True)
    hemi_smoothwm_file = File(exists=True, desc="surf/{hemi}.smoothwm", mandatory=True)
    hemi_curv_file = File(exists=True, desc="surf/{hemi}.curv", mandatory=True)
    hemi_sulc_file = File(exists=True, desc="surf/{hemi}.sulc", mandatory=True)
    threads = traits.Int(desc='threads')

    hemi_curv_stats_file = File(exists=False, desc="stats/{hemi}.curv.stats", mandatory=True)


class CurvstatsOutputSpec(TraitedSpec):
    hemi_curv_stats_file = File(exists=False, desc="stats/{hemi}.curv.stats", mandatory=True)


class Curvstats(BaseInterface):
    input_spec = CurvstatsInputSpec
    output_spec = CurvstatsOutputSpec

    time = 3.1 / 60  # 运行时间：分钟 / 单脑测试时间
    cpu = 2  # 最大cpu占用：个
    gpu = 0  # 最大gpu占用：MB

    def _run_interface(self, runtime):
        threads = self.inputs.threads if self.inputs.threads else 0
        fsthreads = get_freesurfer_threads(threads)

        # in FS7 curvstats moves here
        cmd = f"recon-all -subject {self.inputs.subject_id} -hemi {self.inputs.hemi} -curvstats -no-isrunning {fsthreads}"
        run_cmd_with_timing(cmd)

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["hemi_curv_stats_file"] = self.inputs.hemi_curv_stats_file


class CortribbonInputSpec(BaseInterfaceInputSpec):
    subjects_dir = Directory(exists=True, desc="subject dir", mandatory=True)
    subject_id = Str(desc="subject id", mandatory=True)
    threads = traits.Int(desc='threads')
    aseg_presurf_file = File(exists=True, desc="mri/aseg.presurf.mgz", mandatory=True)
    hemi = Str(desc="lh/rh", mandatory=True)
    hemi_white = File(exists=True, desc="surf/{hemi}.white", mandatory=True)
    hemi_pial = File(exists=True, desc="surf/{hemi}.pial", mandatory=True)

    hemi_ribbon = File(exists=False, desc="mri/{hemi}.ribbon.mgz", mandatory=True)
    ribbon = File(exists=False, desc="mri/ribbon.mgz", mandatory=True)


class CortribbonOutputSpec(TraitedSpec):
    hemi_ribbon = File(exists=False, desc="mri/{hemi}.ribbon.mgz", mandatory=True)
    ribbon = File(exists=False, desc="mri/ribbon.mgz", mandatory=True)


class Cortribbon(BaseInterface):
    input_spec = CortribbonInputSpec
    output_spec = CortribbonOutputSpec

    time = 203 / 60  # 运行时间：分钟 / 单脑测试时间
    cpu = 3.5  # 最大cpu占用：个
    gpu = 0  # 最大gpu占用：MB

    def _run_interface(self, runtime):
        threads = self.inputs.threads if self.inputs.threads else 0
        fsthreads = get_freesurfer_threads(threads)
        # -cortribbon 4 minutes, ribbon is used in mris_anatomical stats
        # to remove voxels from surface based volumes that should not be cortex
        # anatomical stats can run without ribon, but will omit some surface based measures then
        # wmparc needs ribbon, probably other stuff (aparc to aseg etc).
        # could be stripped but lets run it to have these measures below
        cmd = f"recon-all -subject {self.inputs.subject_id} -cortribbon {fsthreads}"
        run_cmd_with_timing(cmd)

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["hemi_ribbon"] = self.inputs.hemi_ribbon
        outputs["ribbon"] = self.inputs.ribbon

