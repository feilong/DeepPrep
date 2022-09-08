from pathlib import Path
from nipype.interfaces.base import BaseInterfaceInputSpec, BaseInterface, File, TraitedSpec, Directory, \
    traits, traits_extension, Str
from run import run_cmd_with_timing


class SegmentInputSpec(BaseInterfaceInputSpec):
    python_interpret = File(exists=True, mandatory=True, desc='the python interpret to use')
    in_file = File(exists=True, mandatory=True, desc='name of file to process. Default: mri/orig.mgz')
    out_file = File(mandatory=True,
                    desc='name under which segmentation will be saved. Default: mri/aparc.DKTatlas+aseg.deep.mgz. '
                         'If a separate subfolder is desired (e.g. FS conform, add it to the name: '
                         'mri/aparc.DKTatlas+aseg.deep.mgz)')  # Do not set exists=True !!
    conformed_file = File(desc='Name under which the conformed input image will be saved, in the same directory as '
                               'the segmentation (the input image is always conformed first, if it is not already '
                               'conformed). The original input image is saved in the output directory as '
                               '$id/mri/orig/001.mgz. Default: mri/conform.mgz.')
    eval_py = File(exists=True, mandatory=True, desc="FastSurfer segmentation script")
    network_sagittal_path = File(exists=True, mandatory=True, desc="path to pre-trained weights of sagittal network")
    network_coronal_path = File(exists=True, mandatory=True, desc="pre-trained weights of coronal network")
    network_axial_path = File(exists=True, mandatory=True, desc="pre-trained weights of axial network")


class SegmentOutputSpec(TraitedSpec):
    aseg_deep_file = File(exists=True, desc='the output seg image: mri/aparc.DKTatlas+aseg.deep.mgz')


class Segment(BaseInterface):
    input_spec = SegmentInputSpec
    output_spec = SegmentOutputSpec

    time = 24 / 60  # 运行时间：分钟
    cpu = 10  # 最大cpu占用：个
    gpu = 9756  # 最大gpu占用：MB

    def _run_interface(self, runtime):
        if not traits_extension.isdefined(self.inputs.conformed_file):
            conformed_file = Path(self.inputs.out_file).parent / 'conformed.mgz'
        else:
            conformed_file = self.inputs.conformed_file
        cmd = f'{self.inputs.python_interpret} {self.inputs.eval_py} ' \
              f'--in_name {self.inputs.in_file} ' \
              f'--out_name {self.inputs.out_file} ' \
              f'--conformed_name {conformed_file} ' \
              '--order 1 ' \
              f'--network_sagittal_path {self.inputs.network_sagittal_path} ' \
              f'--network_coronal_path {self.inputs.network_coronal_path} ' \
              f'--network_axial_path {self.inputs.network_axial_path} ' \
              '--batch_size 1 --simple_run --run_viewagg_on check'
        run_cmd_with_timing(cmd)
        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['aseg_deep_file'] = self.inputs.out_file
        return outputs


class N4BiasCorrectInputSpec(BaseInterfaceInputSpec):
    python = traits.Str(exists=True, desc="default: python3", mandatory=True)
    orig_file = File(exists=True, desc="mri/orig.mgz", mandatory=True)
    orig_nu_file = File(desc="mri/orig_nu.mgz", mandatory=True)
    mask_file = File(exists=True, desc="mri/mask.mgz", mandatory=True)
    threads = traits.Int(desc="threads")


class N4BiasCorrectOutputSpec(TraitedSpec):
    nu_file = File(exists=True, desc="mri/orig_nu.mgz")


class N4BiasCorrect(BaseInterface):
    input_spec = N4BiasCorrectInputSpec
    output_spec = N4BiasCorrectOutputSpec

    time = 7 / 60  # per minute
    cpu = 10
    gpu = 0

    def __init__(self, fastsurfer_home: Path):
        super(N4BiasCorrect, self).__init__()
        self.fastsurfer_bin = fastsurfer_home / "recon_surf"

    def _run_interface(self, runtime):
        # orig_nu nu correct
        if not traits_extension.isdefined(self.inputs.threads):
            self.inputs.threads = 1

        py = self.fastsurfer_bin / "N4_bias_correct.py"
        cmd = f"{self.inputs.python} {py} --in {self.inputs.orig_file} --out {self.inputs.orig_nu_file} " \
              f"--mask {self.inputs.mask_file}  --threads {self.inputs.threads}"
        run_cmd_with_timing(cmd)

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['nu_file'] = self.inputs.orig_nu_file


class TalairachAndNuInputSpec(BaseInterfaceInputSpec):
    sub_mri_dir = Directory(exists=True, desc="subject path", mandatory=True)
    threads = traits.Int(desc="threads")
    orig_nu_file = File(exists=True, desc="mri/orig_nu.mgz", mandatory=True)
    talairach_auto_xfm = File(exists=True, desc="mri/transforms/talairach.auto.xfm", value=None)
    talairach_xfm = File(exists=True, desc="mri/transforms/talairach.xfm", mandatory=True)
    orig_file = File(exists=True, desc="mri/orig.mgz", mandatory=True)
    talairach_xfm_lta = File(exists=True, desc="mri/transforms/talairach.xfm.lta", mandatory=True)
    talairach_lta = File(exists=True, desc="mri/transforms/talairach.lta")
    talairach_skull_lta = File(exists=True, desc="mri/transforms/talairach_with_skull.lta")

    nu_file = File(desc="mri/nu.mgz", mandatory=True)


class TalairachAndNuOutputSpec(TraitedSpec):
    talairach_lta = File(exists=True, desc="mri/transforms/talairach.lta")
    nu_file = File(exists=True, desc="mri/nu.mgz")


class TalairachAndNu(BaseInterface):
    input_spec = TalairachAndNuInputSpec
    output_spec = TalairachAndNuOutputSpec

    time = 18 / 60
    cpu = 1
    gpu = 0

    def __init__(self, freesurfer_home: Path):
        super(TalairachAndNu, self).__init__()
        self.mni305 = freesurfer_home / "average" / "mni305.cor.mgz"

    def _run_interface(self, runtime):
        if self.inputs.threads is None:
            self.inputs.threads = 1
        if not traits_extension.isdefined(self.inputs.talairach_auto_xfm):
            self.inputs.talairach_auto_xfm = Path(self.inputs.sub_mri_dir) / "transforms" / "talairach.auto.xfm"
        if not traits_extension.isdefined(self.inputs.talairach_lta):
            self.inputs.talairach_lta = Path(self.inputs.sub_mri_dir) / "transforms" / "talairach.lta"
        if not traits_extension.isdefined(self.inputs.talairach_skull_lta):
            self.inputs.talairach_skull_lta = Path(self.inputs.sub_mri_dir) / "transforms" / "talairach_with_skull.lta"

        # talairach.xfm: compute talairach full head (25sec)
        cmd = f'cd {self.inputs.sub_mri_dir} && ' \
              f'talairach_avi --i {self.inputs.orig_nu_file} --xfm {self.inputs.talairach_auto_xfm}'
        run_cmd_with_timing(cmd)
        cmd = f'cp {self.inputs.talairach_auto_xfm} {self.inputs.talairach_xfm}'
        run_cmd_with_timing(cmd)

        # talairach.lta:  convert to lta
        cmd = f"lta_convert --src {self.inputs.orig_file} --trg {self.mni305} " \
              f"--inxfm {self.inputs.talairach_xfm} --outlta {self.inputs.talairach_xfm_lta} " \
              f"--subject fsaverage --ltavox2vox"
        run_cmd_with_timing(cmd)

        # Since we do not run mri_em_register we sym-link other talairach transform files here
        cmd = f"cp {self.inputs.talairach_xfm_lta} {self.inputs.talairach_skull_lta}"
        run_cmd_with_timing(cmd)
        cmd = f"cp {self.inputs.talairach_xfm_lta} {self.inputs.talairach_lta}"
        run_cmd_with_timing(cmd)

        # Add xfm to nu
        cmd = f'mri_add_xform_to_header -c {self.inputs.talairach_xfm} {self.inputs.orig_nu_file} {self.inputs.nu_file}'
        run_cmd_with_timing(cmd)

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["talairach_lta"] = self.inputs.talairach_lta
        outputs['nu_file'] = self.inputs.nu_file
        return outputs


class NoccsegThresholdInputSpec(BaseInterfaceInputSpec):
    python_interpret = File(exists=True, mandatory=True, desc='the python interpret to use')
    mask_file = File(exists=True, mandatory=True, desc='mask.mgz')
    in_file = File(exists=True, mandatory=True, desc='name of file to process. Default: aparc.DKTatlas+aseg.orig.mgz')
    out_file = File(mandatory=True,
                    desc='Default: aseg.auto_noCCseg.mgz'
                         'reduce labels to aseg, then create mask (dilate 5, erode 4, largest component), '
                         'also mask aseg to remove outliers'
                         'output will be uchar (else mri_cc will fail below)')  # Do not set exists=True !!
    reduce_to_aseg_py = File(exists=True, mandatory=True, desc="reduce to aseg")


class NoccsegThresholdOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc="aseg.auto_noCCseg.mgz")


class Noccseg(BaseInterface):
    input_spec = NoccsegThresholdInputSpec
    output_spec = NoccsegThresholdOutputSpec

    time = 21 / 60  # 运行时间：分钟
    cpu = 1  # 最大cpu占用：个
    gpu = 0  # 最大gpu占用：MB

    def _run_interface(self, runtime):
        cmd = f'{self.inputs.python_interpret} {self.inputs.reduce_to_aseg_py} ' \
              f'-i {self.inputs.in_file} ' \
              f'-o {self.inputs.out_file} --outmask {self.inputs.mask_file} --fixwm'
        run_cmd_with_timing(cmd)
        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['out_file'] = self.inputs.out_file
        return outputs


class UpdateAsegInputSpec(BaseInterfaceInputSpec):
    subject_dir = Directory(exists=True, desc="subject dir", mandatory=True)
    subject_id = Str(desc="subject id", mandatory=True)
    python_interpret = File(exists=True, desc="python interpret", mandatory=True)
    paint_cc_file = File(exists=True, desc="FastSurfer/recon_surf/paint_cc_into_pred.py", mandatory=True)
    aseg_noCCseg_file = File(exists=True, desc="mri/aseg.auto_noCCseg.mgz", mandatory=True)
    seg_file = File(exists=True, desc="mri/aparc.DKTatlas+aseg.deep.mgz", mandatory=True)

    aseg_auto_file = File(exists=False, desc="mri/aseg.auto.mgz", mandatory=True)
    cc_up_file = File(exists=False, desc="mri/transforms/cc_up.lta", mandatory=True)
    aparc_aseg_file = File(exists=False, desc="mri/aparc.DKTatlas+aseg.deep.withCC.mgz", mandatory=True)


class UpdateAsegOutputSpec(TraitedSpec):
    aseg_auto_file = File(exists=False, desc="mri/aseg.auto.mgz", mandatory=True)
    cc_up_file = File(exists=False, desc="mri/transforms/cc_up.lta", mandatory=True)
    aparc_aseg_file = File(exists=False, desc="mri/aparc.DKTatlas+aseg.deep.withCC.mgz", mandatory=True)


class UpdateAseg(BaseInterface):
    input_spec = UpdateAsegInputSpec
    output_spec = UpdateAsegOutputSpec

    time = 21 / 60  # 运行时间：分钟
    cpu = 1.6  # 最大cpu占用：个
    gpu = 0  # 最大gpu占用：MB

    def _run_interface(self, runtime):
        # create aseg.auto including cc segmentation and add cc into aparc.DKTatlas+aseg.deep;
        # 46 sec: (not sure if this is needed), requires norm.mgz
        cmd = f'mri_cc -aseg aseg.auto_noCCseg.mgz -o aseg.auto.mgz ' \
              f'-lta {self.inputs.cc_up_file} {self.inputs.subject_id}'
        run_cmd_with_timing(cmd)

        # 0.8s
        cmd = f'{self.inputs.python_interpret} {self.inputs.paint_cc_file} ' \
              f'-in_cc {self.inputs.aseg_auto_file} -in_pred {self.inputs.seg_file} ' \
              f'-out {self.inputs.aparc_aseg_file}'
        run_cmd_with_timing(cmd)

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["aseg_auto_file"] = self.inputs.aseg_auto_file
        outputs["cc_up_file"] = self.inputs.cc_up_file
        outputs["aparc_aseg_file"] = self.inputs.aparc_aseg_file


class SampleSegmentationToSurfaveInputSpec(BaseInterfaceInputSpec):
    subject_dir = Directory(exists=True, desc="subject dir", mandatory=True)
    subject_id = Str(desc="subject id", mandatory=True)
    python_interpret = File(exists=True, desc="python interpret", mandatory=True)
    freesufer_home = Directory(exists=True, desc="freesufer_home", mandatory=True)
    hemi = Str(desc="lh/rh", mandatory=True)
    hemi_DKTatlaslookup_file = File(exists=True, desc="FastSurfer/recon_surf/{hemi}.DKTatlaslookup.txt", mandatory=True)
    aparc_aseg_file = File(exists=True, desc="mri/aparc.DKTatlas+aseg.deep.withCC.mgz", mandatory=True)
    smooth_aparc_file = File(exists=True, desc="Fastsurfer/recon_surf/smooth_aparc.py", mandatory=True)
    hemi_white_preaparc_file = File(exists=True, desc="surf/{hemi}.white.preaparc", mandatory=True)
    hemi_cortex_label_file = File(exists=True, desc="label/{hemi}.cortex.label", mandatory=True)

    hemi_aparc_DKTatlas_mapped_prefix_file = File(exists=False, desc="label/{hemi}.aparc.DKTatlas.mapped.prefix.annot",
                                                  mandatory=True)
    hemi_aparc_DKTatlas_mapped_file = File(exists=False, desc="label/{hemi}.aparc.DKTatlas.mapped.annot",
                                           mandatory=True)


class SampleSegmentationToSurfaveOutputSpec(TraitedSpec):
    hemi_aparc_DKTatlas_mapped_prefix_file = File(exists=False, desc="label/{hemi}.aparc.DKTatlas.mapped.prefix.annot",
                                                  mandatory=True)
    hemi_aparc_DKTatlas_mapped_file = File(exists=False, desc="label/{hemi}.aparc.DKTatlas.mapped.annot",
                                           mandatory=True)


class SampleSegmentationToSurfave(BaseInterface):
    input_spec = SampleSegmentationToSurfaveInputSpec
    output_spec = SampleSegmentationToSurfaveOutputSpec

    time = 11 / 60  # 运行时间：分钟 / 单脑测试时间
    cpu = 3.5  # 最大cpu占用：个
    gpu = 0  # 最大gpu占用：MB

    def _run_interface(self, runtime):
        # sample input segmentation (aparc.DKTatlas+aseg orig) onto wm surface:
        # map input aparc to surface (requires thickness (and thus pail) to compute projfrac 0.5),
        # here we do projmm which allows us to compute based only on white
        # this is dangerous, as some cortices could be < 0.6 mm, but then there is no volume label probably anyway.
        # Also note that currently we cannot mask non-cortex regions here, should be done in mris_anatomical stats later
        # the smoothing helps
        cmd = f"mris_sample_parc -ct {self.inputs.freesufer_home}/average/colortable_desikan_killiany.txt " \
              f"-file {self.inputs.hemi_DKTatlaslookup_file} -projmm 0.6 -f 5  " \
              f"-surf white.preaparc {self.inputs.subject_id} {self.inputs.hemi} " \
              f"aparc.DKTatlas+aseg.orig.mgz aparc.DKTatlas.mapped.prefix.annot"
        run_cmd_with_timing(cmd)

        cmd = f"{self.inputs.python_interpret} {self.inputs.smooth_aparc_file} " \
              f"--insurf {self.inputs.hemi_white_preaparc_file} " \
              f"--inaparc {self.inputs.hemi_aparc_DKTatlas_mapped_prefix_file} " \
              f"--incort {self.inputs.hemi_cortex_label_file} " \
              f"--outaparc {self.inputs.hemi_aparc_DKTatlas_mapped_file}"
        run_cmd_with_timing(cmd)

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["hemi_aparc_DKTatlas_mapped_prefix_file"] = self.inputs.hemi_aparc_DKTatlas_mapped_prefix_file
        outputs["hemi_aparc_DKTatlas_mapped_file"] = self.inputs.hemi_aparc_DKTatlas_mapped_file