# ---------------------------- SPECIFIC FUNCTIONS ---------------------------- #

#   Noninteractive update
def auto_upgrade(snapshot):
    sync_time() # Required in virtualbox, otherwise error in package db update
    prepare(snapshot)
    excode = os.system(f"chroot /.snapshots/rootfs/snapshot-chr{snapshot} apt-get update -y")
    if excode == 0:
        post_transactions(snapshot)
        os.system("echo 0 > /.snapshots/ash/upstate")
        os.system("echo $(date) >> /.snapshots/ash/upstate")
    else:
        chr_delete(snapshot)
        os.system("echo 1 > /.snapshots/ash/upstate")
        os.system("echo $(date) >> /.snapshots/ash/upstate")

#   Copy cache of downloaded packages to shared
def cache_copy(snapshot, FROM):
    os.system(f"cp -n -r --reflink=auto /.snapshots/rootfs/snapshot-chr{snapshot}/var/cache/apt/. /var/cache/apt/{DEBUG}")

#   Fix signature invalid error
def fix_package_db(snapshot = "0"):
    return 0

#   Delete init system files (Systemd, OpenRC, etc.)
def init_system_clean(snapshot, FROM):
    if FROM == "prepare":
        os.system(f"rm -rf /.snapshots/rootfs/snapshot-chr{snapshot}/var/lib/systemd/*{DEBUG}")
    elif FROM == "deploy":
        os.system(f"rm -rf /var/lib/systemd/*{DEBUG}")
        os.system(f"rm -rf /.snapshots/rootfs/snapshot-{snapshot}/var/lib/systemd/*{DEBUG}")

#   Copy init system files (Systemd, OpenRC, etc.) to shared
def init_system_copy(snapshot, FROM):
    if FROM == "post_transactions":
        os.system(f"rm -rf /var/lib/systemd/*{DEBUG}")
        os.system(f"cp -r --reflink=auto /.snapshots/rootfs/snapshot-{snapshot}/var/lib/systemd/. /var/lib/systemd/{DEBUG}")

#   Install atomic-operation
def install_package(snapshot, pkg):
    prepare(snapshot)
    return os.system(f"chroot /.snapshots/rootfs/snapshot-chr{snapshot} apt-get install -f -y {pkg}") ### -o Dpkg::Options::="--force-overwrite" TODO: --overwrite '/var/*'

#   Install atomic-operation in live snapshot
def install_package_live(snapshot, tmp, pkg):
    #options = snapshot_config_get(tmp)
    return os.system(f"chroot /.snapshots/rootfs/snapshot-{tmp} apt-get install -y {pkg}{DEBUG}") ### TODO: --overwrite \\*

#   Get list of packages installed in a snapshot
def pkg_list(CHR, snap):
    return subprocess.check_output(f"chroot /.snapshots/rootfs/snapshot-{CHR}{snap} dpkg -l | grep '^.i' | awk '{{print $2}}'", encoding='utf-8', shell=True).strip().split("\n")

#   Refresh snapshot atomic-operation
def refresh_helper(snapshot):
    return os.system(f"chroot /.snapshots/rootfs/snapshot-chr{snapshot} apt-get update")

#   Show diff of packages between 2 snapshots TODO: make this function not depend on bash
def snapshot_diff(snap1, snap2):
    if not os.path.exists(f"/.snapshots/rootfs/snapshot-{snap1}"):
        print(f"Snapshot {snap1} not found.")
    elif not os.path.exists(f"/.snapshots/rootfs/snapshot-{snap2}"):
        print(f"Snapshot {snap2} not found.")
    else:
        os.system(f"diff -qrly --no-dereference /.snapshots/rootfs/snapshot-{snap1}/usr/share/ash/db/dpkg/info \
                    /.snapshots/rootfs/snapshot-{snap2}/usr/share/ash/db/dpkg/info")

#   Uninstall package(s) atomic-operation
def uninstall_package_helper(snapshot, pkg):
    return os.system(f"chroot /.snapshots/rootfs/snapshot-chr{snapshot} apt-get remove {pkg}")

#   Upgrade snapshot atomic-operation
def upgrade_helper(snapshot):
    prepare(snapshot) ### REVIEW tried it outside of this function in ashpk_core before aur_install and it works fine!
    return os.system(f"chroot /.snapshots/rootfs/snapshot-chr{snapshot} apt-get update")

# ---------------------------------------------------------------------------- #

#   Call main
if __name__ == "__main__":
    main()

