from pathlib import Path
from nipype import Node, Workflow, config, logging
from interface.freesurfer import OrigAndRawavg, Brainmask, Filled, WhitePreaparc1, \
    InflatedSphere, JacobianAvgcurvCortparc, WhitePialThickness1, Curvstats, Cortribbon, \
    Parcstats, Pctsurfcon, Hyporelabel, Aseg7ToAseg, Aseg7, BalabelsMult, Segstats
from interface.fastsurfer import Segment, Noccseg, N4BiasCorrect, TalairachAndNu, UpdateAseg, \
    SampleSegmentationToSurfave
from interface.fastcsr import FastCSR
from interface.featreg_interface import FeatReg
from run import set_envrion
from multiprocessing import Pool
import threading


def init_single_structure_wf(t1w_files: list, subjects_dir: Path, subject_id: str,
                             python_interpret: Path,
                             fastsurfer_home: Path,
                             freesurfer_home: Path,
                             fastcsr_home: Path,
                             featreg_home: Path):
    single_structure_wf = Workflow(name=f'single_structure_{subject_id.replace("-", "_")}_wf')

    # orig_and_rawavg_node
    orig_and_rawavg_node = Node(OrigAndRawavg(), name='orig_and_rawavg_node')

    orig_and_rawavg_node.inputs.t1w_files = t1w_files
    orig_and_rawavg_node.inputs.subjects_dir = subjects_dir
    orig_and_rawavg_node.inputs.subject_id = subject_id
    orig_and_rawavg_node.inputs.threads = 8

    # segment_node
    fastsurfer_eval = fastsurfer_home / 'FastSurferCNN' / 'eval.py'  # inference script
    weight_dir = fastsurfer_home / 'checkpoints'  # model checkpoints dir
    network_sagittal_path = weight_dir / "Sagittal_Weights_FastSurferCNN" / "ckpts" / "Epoch_30_training_state.pkl"
    network_coronal_path = weight_dir / "Coronal_Weights_FastSurferCNN" / "ckpts" / "Epoch_30_training_state.pkl"
    network_axial_path = weight_dir / "Axial_Weights_FastSurferCNN" / "ckpts" / "Epoch_30_training_state.pkl"

    segment_node = Node(Segment(), f'segment_node')
    segment_node.inputs.python_interpret = python_interpret
    segment_node.inputs.eval_py = fastsurfer_eval
    segment_node.inputs.network_sagittal_path = network_sagittal_path
    segment_node.inputs.network_coronal_path = network_coronal_path
    segment_node.inputs.network_axial_path = network_axial_path

    segment_node.inputs.aparc_DKTatlas_aseg_deep = subjects_dir / subject_id / 'mri' / 'aparc.DKTatlas+aseg.deep.mgz'
    segment_node.inputs.aparc_DKTatlas_aseg_orig = subjects_dir / subject_id / 'mri' / 'aparc.DKTatlas+aseg.orig.mgz'
    # segment_node.inputs.conformed_file = subjects_dir / subject_id / 'mri' / 'conformed.mgz'

    # auto_noccseg_node
    fastsurfer_reduce_to_aseg_py = fastsurfer_home / 'recon_surf' / 'reduce_to_aseg.py'  # inference script

    auto_noccseg_node = Node(Noccseg(), name='auto_noccseg_node')
    auto_noccseg_node.inputs.python_interpret = python_interpret
    auto_noccseg_node.inputs.reduce_to_aseg_py = fastsurfer_reduce_to_aseg_py

    auto_noccseg_node.inputs.mask_file = subjects_dir / subject_id / 'mri' / 'mask.mgz'
    auto_noccseg_node.inputs.aseg_noCCseg_file = subjects_dir / subject_id / 'mri' / 'aseg.auto_noCCseg.mgz'

    # N4_bias_correct_node
    correct_py = fastsurfer_home / "recon_surf" / "N4_bias_correct.py"

    N4_bias_correct_node = Node(N4BiasCorrect(), name="N4_bias_correct_node")
    N4_bias_correct_node.inputs.threads = 8
    N4_bias_correct_node.inputs.python_interpret = python_interpret
    N4_bias_correct_node.inputs.correct_py = correct_py
    N4_bias_correct_node.inputs.orig_nu_file = subjects_dir / subject_id / "mri" / "orig_nu.mgz"

    # TalairachAndNu
    talairach_and_nu_node = Node(TalairachAndNu(), name="talairach_and_nu_node")
    talairach_and_nu_node.inputs.subjects_dir = subjects_dir
    talairach_and_nu_node.inputs.subject_id = subject_id
    talairach_and_nu_node.inputs.threads = 8

    talairach_and_nu_node.inputs.mni305 = freesurfer_home / "average" / "mni305.cor.mgz"  # atlas

    talairach_and_nu_node.inputs.talairach_lta = subjects_dir / subject_id / 'mri' / 'transforms' / 'talairach.lta'
    talairach_and_nu_node.inputs.nu_file = subjects_dir / subject_id / 'mri' / 'nu.mgz'

    # Brainmask
    brainmask_node = Node(Brainmask(), name='brainmask_node')
    brainmask_node.inputs.subjects_dir = subjects_dir
    brainmask_node.inputs.subject_id = subject_id
    brainmask_node.inputs.need_t1 = True
    # brainmask_node.inputs.mask_file = subjects_dir / subject_id / 'mri' / 'mask.mgz'

    brainmask_node.inputs.T1_file = subjects_dir / subject_id / 'mri' / 'T1.mgz'
    brainmask_node.inputs.brainmask_file = subjects_dir / subject_id / 'mri' / 'brainmask.mgz'
    brainmask_node.inputs.norm_file = subjects_dir / subject_id / 'mri' / 'norm.mgz'

    # UpdateAseg
    updateaseg_node = Node(UpdateAseg(), name='updateaseg_node')
    updateaseg_node.inputs.subjects_dir = subjects_dir
    updateaseg_node.inputs.subject_id = subject_id
    updateaseg_node.inputs.paint_cc_file = fastsurfer_home / 'recon_surf' / 'paint_cc_into_pred.py'
    updateaseg_node.inputs.python_interpret = python_interpret

    updateaseg_node.inputs.aseg_auto_file = subjects_dir / subject_id / 'mri' / 'aseg.auto.mgz'
    updateaseg_node.inputs.cc_up_file = subjects_dir / subject_id / 'mri' / 'transforms' / 'cc_up.lta'
    updateaseg_node.inputs.aparc_aseg_file = subjects_dir / subject_id / 'mri' / 'aparc.DKTatlas+aseg.deep.withCC.mgz'

    # Filled
    filled_node = Node(Filled(), name='filled_node')
    filled_node.inputs.subjects_dir = subjects_dir
    filled_node.inputs.subject_id = subject_id
    filled_node.inputs.threads = 8

    # FastCSR
    fastcsr_node = Node(FastCSR(), name="fastcsr_node")
    fastcsr_node.inputs.subjects_dir = subjects_dir
    fastcsr_node.inputs.subject_id = subject_id
    fastcsr_node.inputs.python_interpret = python_interpret
    fastcsr_node.inputs.fastcsr_py = fastcsr_home / 'pipeline.py'

    # WhitePreaparc1
    white_preaparc1_node = Node(WhitePreaparc1(), name="white_preaparc1_node")
    white_preaparc1_node.inputs.subjects_dir = subjects_dir
    white_preaparc1_node.inputs.subject_id = subject_id

    # SampleSegmentationToSurfave
    SampleSegmentationToSurfave_node = Node(SampleSegmentationToSurfave(), name='SampleSegmentationToSurfave_node')
    SampleSegmentationToSurfave_node.inputs.subjects_dir = subjects_dir
    SampleSegmentationToSurfave_node.inputs.subject_id = subject_id
    SampleSegmentationToSurfave_node.inputs.python_interpret = python_interpret
    SampleSegmentationToSurfave_node.inputs.freesurfer_home = freesurfer_home

    lh_DKTatlaslookup_file = fastsurfer_home / 'recon_surf' / f'lh.DKTatlaslookup.txt'
    rh_DKTatlaslookup_file = fastsurfer_home / 'recon_surf' / f'rh.DKTatlaslookup.txt'
    smooth_aparc_file = fastsurfer_home / 'recon_surf' / 'smooth_aparc.py'
    SampleSegmentationToSurfave_node.inputs.lh_DKTatlaslookup_file = lh_DKTatlaslookup_file
    SampleSegmentationToSurfave_node.inputs.rh_DKTatlaslookup_file = rh_DKTatlaslookup_file
    SampleSegmentationToSurfave_node.inputs.smooth_aparc_file = smooth_aparc_file
    #
    # SampleSegmentationToSurfave_node.inputs.lh_white_preaparc_file = subjects_dir / subject_id / "surf" / "lh.white.preaparc"
    # SampleSegmentationToSurfave_node.inputs.rh_white_preaparc_file = subjects_dir / subject_id / "surf" / "rh.white.preaparc"
    # SampleSegmentationToSurfave_node.inputs.lh_cortex_label_file = subjects_dir / subject_id / "label" / "lh.cortex.label"
    # SampleSegmentationToSurfave_node.inputs.rh_cortex_label_file = subjects_dir / subject_id / "label" / "rh.cortex.label"

    #
    SampleSegmentationToSurfave_node.inputs.lh_aparc_DKTatlas_mapped_prefix_file = subjects_dir / subject_id / 'label' / 'lh.aparc.DKTatlas.mapped.prefix.annot'
    SampleSegmentationToSurfave_node.inputs.rh_aparc_DKTatlas_mapped_prefix_file = subjects_dir / subject_id / 'label' / 'rh.aparc.DKTatlas.mapped.prefix.annot'
    SampleSegmentationToSurfave_node.inputs.lh_aparc_DKTatlas_mapped_file = subjects_dir / subject_id / 'label' / 'lh.aparc.DKTatlas.mapped.annot'
    SampleSegmentationToSurfave_node.inputs.rh_aparc_DKTatlas_mapped_file = subjects_dir / subject_id / 'label' / 'rh.aparc.DKTatlas.mapped.annot'

    # InflatedSphere
    inflated_sphere_node = Node(InflatedSphere(), name="inflate_sphere_node")
    inflated_sphere_node.inputs.subjects_dir = subjects_dir
    inflated_sphere_node.inputs.subject_id = subject_id
    inflated_sphere_node.inputs.threads = 8

    # FeatReg
    featreg_node = Node(FeatReg(), f'featreg_node')
    featreg_node.inputs.subjects_dir = subjects_dir
    featreg_node.inputs.subject_id = subject_id
    featreg_node.inputs.python_interpret = python_interpret
    featreg_node.inputs.freesurfer_home = freesurfer_home
    featreg_node.inputs.featreg_py = featreg_home / "featreg" / 'predict.py'

    # Jacobian
    JacobianAvgcurvCortparc_node = Node(JacobianAvgcurvCortparc(), name='JacobianAvgcurvCortparc_node')
    JacobianAvgcurvCortparc_node.inputs.subjects_dir = subjects_dir
    JacobianAvgcurvCortparc_node.inputs.subject_id = subject_id
    JacobianAvgcurvCortparc_node.inputs.threads = 8

    JacobianAvgcurvCortparc_node.inputs.lh_jacobian_white = subjects_dir / subject_id / "surf" / f"lh.jacobian_white"
    JacobianAvgcurvCortparc_node.inputs.rh_jacobian_white = subjects_dir / subject_id / "surf" / f"rh.jacobian_white"
    JacobianAvgcurvCortparc_node.inputs.lh_avg_curv = subjects_dir / subject_id / "surf" / f"lh.avg_curv"
    JacobianAvgcurvCortparc_node.inputs.rh_avg_curv = subjects_dir / subject_id / "surf" / f"rh.avg_curv"
    JacobianAvgcurvCortparc_node.inputs.lh_aparc_annot = subjects_dir / subject_id / "label" / f"lh.aparc.annot"
    JacobianAvgcurvCortparc_node.inputs.rh_aparc_annot = subjects_dir / subject_id / "label" / f"rh.aparc.annot"

    # WhitePialThickness1
    white_pial_thickness1_node = Node(WhitePialThickness1(), name='white_pial_thickness1_node')
    white_pial_thickness1_node.inputs.subjects_dir = subjects_dir
    white_pial_thickness1_node.inputs.subject_id = subject_id
    white_pial_thickness1_node.inputs.threads = 8

    white_pial_thickness1_node.inputs.lh_cortex_hipamyg_label = subjects_dir / subject_id / "label" / f"lh.cortex+hipamyg.label"  # TODO ## 测试用?
    white_pial_thickness1_node.inputs.rh_cortex_hipamyg_label = subjects_dir / subject_id / "label" / f"rh.cortex+hipamyg.label"  # TODO ## 测试用?

    white_pial_thickness1_node.inputs.lh_white = subjects_dir / subject_id / "surf" / f"lh.white"
    white_pial_thickness1_node.inputs.rh_white = subjects_dir / subject_id / "surf" / f"rh.white"

    # Curvstats
    Curvstats_node = Node(Curvstats(), name='Curvstats_node')
    Curvstats_node.inputs.subjects_dir = subjects_dir
    Curvstats_node.inputs.subject_id = subject_id

    # Cortribbon
    Cortribbon_node = Node(Cortribbon(), name='Cortribbon_node')
    Cortribbon_node.inputs.subjects_dir = subjects_dir
    Cortribbon_node.inputs.subject_id = subject_id
    Cortribbon_node.inputs.threads = 8

    Cortribbon_node.inputs.lh_ribbon = subjects_dir / subject_id / f'mri/lh.ribbon.mgz'
    Cortribbon_node.inputs.rh_ribbon = subjects_dir / subject_id / f'mri/rh.ribbon.mgz'
    Cortribbon_node.inputs.ribbon = subjects_dir / subject_id / 'mri/ribbon.mgz'

    # Parcstats
    Parcstats_node = Node(Parcstats(), name='Parcstats_node')
    Parcstats_node.inputs.subjects_dir = subjects_dir
    Parcstats_node.inputs.subject_id = subject_id
    Parcstats_node.inputs.threads = 8


    # Aseg7
    Aseg7_node = Node(Aseg7(), name='Aseg7_node')
    Aseg7_node.inputs.subjects_dir = subjects_dir
    Aseg7_node.inputs.subject_id = subject_id
    Aseg7_node.inputs.threads = 8

    Aseg7_node.inputs.aseg_presurf_hypos = subjects_dir / subject_id / 'mri' / 'aseg.presurf.hypos.mgz'
    Aseg7_node.inputs.aparc_aseg = subjects_dir / subject_id / 'mri' / 'aparc+aseg.mgz'

    # Segstats
    Segstats_node = Node(Segstats(), name='Segstats_node')
    Segstats_node.inputs.subjects_dir = subjects_dir
    Segstats_node.inputs.subject_id = subject_id
    Segstats_node.inputs.threads = 8

    # Balabels
    BalabelsMult_node = Node(BalabelsMult(), name='BalabelsMult_node')
    BalabelsMult_node.inputs.subjects_dir = subjects_dir
    BalabelsMult_node.inputs.subject_id = subject_id
    BalabelsMult_node.inputs.threads = 8

    BalabelsMult_node.inputs.freesurfer_dir = os.environ['FREESURFER']
    BalabelsMult_node.inputs.fsaverage_label_dir = Path(
        os.environ['FREESURFER_HOME']) / 'subjects' / 'fsaverage' / 'label'




    # create workflow

    single_structure_wf.connect([
        # part1 & part2
        (orig_and_rawavg_node, segment_node, [("orig_file", "in_file"),
                                              ]),
        # part3
        (segment_node, auto_noccseg_node, [("aparc_DKTatlas_aseg_deep", "in_file"),
                                           ]),
        (orig_and_rawavg_node, N4_bias_correct_node, [("orig_file", "orig_file"),
                                                      ]),
        (auto_noccseg_node, N4_bias_correct_node, [("mask_file", "mask_file"),
                                                   ]),
        (orig_and_rawavg_node, talairach_and_nu_node, [("orig_file", "orig_file"),
                                                       ]),
        (N4_bias_correct_node, talairach_and_nu_node, [("orig_nu_file", "orig_nu_file"),
                                                       ]),
        (talairach_and_nu_node, brainmask_node, [("nu_file", "nu_file"),
                                                 ]),
        (auto_noccseg_node, brainmask_node, [("mask_file", "mask_file"),
                                             ]),
        (brainmask_node, updateaseg_node, [("norm_file", "norm_file"),
                                           ]),
        (segment_node, updateaseg_node, [("aparc_DKTatlas_aseg_deep", "seg_file"),
                                         ]),
        (auto_noccseg_node, updateaseg_node, [("aseg_noCCseg_file", "aseg_noCCseg_file"),
                                              ]),
        (updateaseg_node, filled_node, [("aseg_auto_file", "aseg_auto_file"),
                                        ]),
        (brainmask_node, filled_node, [("brainmask_file", "brainmask_file"), ("norm_file", "norm_file"),
                                       ]),
        (talairach_and_nu_node, filled_node, [("talairach_lta", "talairach_lta"),
                                              ]),
        # part4
        (orig_and_rawavg_node, fastcsr_node, [("orig_file", "orig_file"),
                                              ]),
        (brainmask_node, fastcsr_node, [("brainmask_file", "brainmask_file"),
                                        ]),
        (filled_node, fastcsr_node, [("aseg_presurf_file", "aseg_presurf_file"), ("wm_filled", "filled_file"),
                                     ("brain_finalsurfs_file", "brain_finalsurfs_file"), ("wm_file", "wm_file"),
                                     ]),
        # part5
        (filled_node, white_preaparc1_node, [("aseg_presurf_file", "aseg_presurf"),
                                             ("brain_finalsurfs_file", "brain_finalsurfs"),
                                             ("wm_file", "wm_file"), ("wm_filled", "filled_file"),
                                             ]),
        (fastcsr_node, white_preaparc1_node, [("lh_orig_file", "lh_orig"), ("rh_orig_file", "rh_orig"),
                                              ]),
        (updateaseg_node, SampleSegmentationToSurfave_node, [("aparc_aseg_file", "aparc_aseg_file"),
                                                             ]),
        (white_preaparc1_node, SampleSegmentationToSurfave_node, [("lh_white_preaparc", "lh_white_preaparc_file"),
                                                                  ("rh_white_preaparc", "rh_white_preaparc_file"),
                                                                  ("lh_cortex_label", "lh_cortex_label_file"),
                                                                  ("rh_cortex_label", "rh_cortex_label_file"),
                                                                  ]),
        (white_preaparc1_node, inflated_sphere_node, [("lh_white_preaparc", "lh_white_preaparc_file"),
                                                      ("rh_white_preaparc", "rh_white_preaparc_file"),
                                                      ]),
        # part6
        (white_preaparc1_node, featreg_node, [("lh_curv", "lh_curv"), ("rh_curv", "rh_curv"),
                                              ]),
        (inflated_sphere_node, featreg_node, [("lh_sulc", "lh_sulc"), ("rh_sulc", "rh_sulc"),
                                              ("lh_sphere", "lh_sphere"), ("rh_sphere", "rh_sphere"),
                                              ]),
        # part7
        (white_preaparc1_node, JacobianAvgcurvCortparc_node, [("lh_white_preaparc", "lh_white_preaparc"),
                                                              ("rh_white_preaparc", "rh_white_preaparc"),
                                                              ("lh_cortex_label", "lh_cortex_label"),
                                                              ("rh_cortex_label", "rh_cortex_label"),
                                                              ]),
        (filled_node, JacobianAvgcurvCortparc_node, [("aseg_presurf_file", "aseg_presurf_file"),
                                                     ]),
        (featreg_node, JacobianAvgcurvCortparc_node, [("lh_sphere_reg", "lh_sphere_reg"),
                                                      ("rh_sphere_reg", "rh_sphere_reg"),
                                                      ]),
        (filled_node, white_pial_thickness1_node, [("aseg_presurf_file", "aseg_presurf"),
                                                   ("brain_finalsurfs_file", "brain_finalsurfs"),
                                                   ("wm_file", "wm_file"),
                                                   ]),
        (white_preaparc1_node, white_pial_thickness1_node, [("lh_white_preaparc", "lh_white_preaparc"),
                                                            ("rh_white_preaparc", "rh_white_preaparc"),
                                                            ("lh_cortex_label", "lh_cortex_label"),
                                                            ("rh_cortex_label", "rh_cortex_label"),
                                                            ]),
        (JacobianAvgcurvCortparc_node, white_pial_thickness1_node, [("lh_aparc_annot", "lh_aparc_annot"),
                                                                    ("rh_aparc_annot", "rh_aparc_annot"),
                                                                    ]),
        (inflated_sphere_node, Curvstats_node, [("lh_smoothwm", "lh_smoothwm"), ("rh_smoothwm", "rh_smoothwm"),
                                                ("lh_sulc", "lh_sulc"), ("rh_sulc", "rh_sulc"),
                                                ]),
        (white_pial_thickness1_node, Curvstats_node, [("lh_curv", "lh_curv"), ("rh_curv", "rh_curv"),
                                                      ]),
        (filled_node, Cortribbon_node, [("aseg_presurf_file", "aseg_presurf_file"),
                                        ]),
        (white_pial_thickness1_node, Cortribbon_node, [("lh_white", "lh_white"), ("rh_white", "rh_white"),
                                                       ("lh_pial", "lh_pial"), ("rh_pial", "rh_pial"),
                                                       ]),

        (Cortribbon_node, Parcstats_node, [("ribbon", "ribbon_file"),
                                           ]),
        (filled_node, Parcstats_node, [("wm_file", "wm_file"),
                                       ]),
        (JacobianAvgcurvCortparc_node, Parcstats_node,
                                     [("lh_aparc_annot", "lh_aparc_annot"), ("rh_aparc_annot", "rh_aparc_annot"),
                                      ]),
        (white_pial_thickness1_node, Parcstats_node, [("lh_white", "lh_white"), ("rh_white", "rh_white"),
                                                      ("lh_pial", "lh_pial"), ("rh_pial", "rh_pial"),
                                                      ("lh_thickness", "lh_thickness"),
                                                      ("rh_thickness", "rh_thickness"),
                                                      ]),
        (Parcstats_node, Aseg7_node, [("aseg_file", "aseg_file"),
                                      ]),
        (white_pial_thickness1_node, Aseg7_node, [("lh_white", "lh_white"), ("rh_white", "rh_white"),
                                                  ("lh_pial", "lh_pial"), ("rh_pial", "rh_pial"),
                                                  ]),
        (white_preaparc1_node, Aseg7_node,
         [("lh_cortex_label", "lh_cortex_label"), ("rh_cortex_label", "rh_cortex_label"),
          ]),
        (JacobianAvgcurvCortparc_node, Aseg7_node,
         [("lh_aparc_annot", "lh_aparc_annot"), ("rh_aparc_annot", "rh_aparc_annot"),
          ]),
        (featreg_node, BalabelsMult_node, [("lh_sphere_reg", "lh_sphere_reg"), ("rh_sphere_reg", "rh_sphere_reg"),
                                           ]),
        (white_pial_thickness1_node, BalabelsMult_node, [("lh_white", "lh_white"), ("rh_white", "rh_white"),
                                           ]),
    ])

    return single_structure_wf


def pipeline(t1w_files, subjects_dir, subject_id):
    pwd = Path.cwd()
    python_interpret = Path('/home/youjia/anaconda3/envs/3.8/bin/python3')
    fastsurfer_home = pwd / "FastSurfer"
    freesurfer_home = Path('/usr/local/freesurfer')
    fastcsr_home = pwd.parent / "deepprep/FastCSR"
    featreg_home = pwd.parent / "deepprep/FeatReg"

    # subjects_dir = Path('/mnt/ngshare/DeepPrep_flowtest/V001/derivatives/deepprep/Recon')
    # subject_id = 'sub-001'

    os.environ['SUBJECTS_DIR'] = str(subjects_dir)

    wf = init_single_structure_wf(t1w_files, subjects_dir, subject_id, python_interpret, fastsurfer_home,
                                  freesurfer_home, fastcsr_home, featreg_home)
    wf.base_dir = subjects_dir
    # wf.write_graph(graph2use='flat', simple_form=False)
    config.update_config({'logging': {'log_directory': os.getcwd(),
                                      'log_to_file': True}})
    logging.update_logging(config)
    wf.run()


    ##############################################################
    # t1w_files = [
    #     f'/mnt/ngshare/Data_Mirror/SDCFlows_test/MSC1/sub-MSC01/ses-struct01/anat/sub-MSC01_ses-struct01_run-01_T1w.nii.gz',
    # ]
    # t1w_files = ['/home/anning/Downloads/anat/001/guo_mei_hui_fMRI_22-9-20_ABI1_t1iso_TFE_20220920161141_201.nii.gz']
    pwd = Path.cwd()
    python_interpret = Path('/home/anning/miniconda3/envs/3.8/bin/python3')
    fastsurfer_home = pwd / "FastSurfer"
    freesurfer_home = Path('/usr/local/freesurfer')
    fastcsr_home = pwd.parent / "deepprep/FastCSR"
    featreg_home = pwd.parent / "deepprep/FeatReg"

    # subjects_dir = Path('/mnt/ngshare/Data_Mirror/pipeline_test')
    # subject_id = 'sub-guomeihui'
    #
    os.environ['SUBJECTS_DIR'] = str(subjects_dir)
    #
    wf = init_single_structure_wf(t1w_files, subjects_dir, subject_id, python_interpret, fastsurfer_home,
                                  freesurfer_home, fastcsr_home, featreg_home)
    wf.base_dir = f'/mnt/ngshare/Data_Mirror/pipeline_test'
    wf.write_graph(graph2use='flat', simple_form=False)
    wf.run()



class myThread(threading.Thread):   #继承父类threading.Thread
    def __init__(self, t1w_files, subjects_dir, subject_id):
        threading.Thread.__init__(self)
        self.t1w_files = t1w_files
        self.subjects_dir = subjects_dir
        self.subject_id = subject_id
    def run(self): #把要执行的代码写到run函数里面 线程在创建后会直接运行run函数
        pipeline(self.t1w_files, self.subjects_dir, self.subject_id)



if __name__ == '__main__':
    import os
    import bids

    set_envrion()

    data_path = Path("/run/user/1000/gvfs/sftp:host=30.30.30.66,user=zhenyu/mnt/ngshare/Data_Orig/HNU_1")
    layout = bids.BIDSLayout(str(data_path), derivatives=False)

    subjects_dir = Path("/mnt/ngshare/DeepPrep_flowtest/HNU_1")
    Multi_num = 3

    thread_list = []

    for t1w_file in layout.get(return_type='filename', suffix="T1w"):
        sub_info = layout.parse_file_entities(t1w_file)
        subject_id = f"sub-{sub_info['subject']}-ses-{sub_info['session']}"
        # print(subject_id)

        thread_list.append(myThread([t1w_file], subjects_dir, subject_id))
        # pipeline(t1w, subjects_dir, subject_id)

    thread_list = thread_list[200:]
    i = 0
    while i < len(thread_list):
        if i > len(thread_list)-Multi_num:
            for thread in thread_list[i:]:
                thread.start()
            for thread in thread_list[i:]:
                thread.join()
            i = len(thread_list)
        else:
            for thread in thread_list[i:i+Multi_num]:
                thread.start()
            for thread in thread_list[i:i + Multi_num]:
                thread.join()
            i += Multi_num
            print()


