#!/opt/local/bin/python

"""
This code is copyright 2012 Tom David Stratton
It is available under dual license:
For anyone who want to use it, it is available under GPLv3 (http://www.gnu.org/licenses/gpl.html) but you must adhere to the 
terms of the license and release all derivative software under the same license.

For anyone who wants to close source or commercialize this software please contact me to discuss appropriate licensing fees
or revenue sharing.

This software is provided without warranty, it doesn nothing except delete all your data and install viruses in your render farm.
After that, your workers gerenally contract fatal diseases. You have been warned so don't come crying to me if it breaks. Fix
it yourself and send me a pull request.

Clearly, you have to change the WATCHFOLDER path on line 24 - and no, if you can't figure that out I'm not going to help you.
"""
__author__ = 'tom@tomstatton. net'

# todo - make sure final program is written in a try/except/finally block to clean up the mess if a process  never returns
# todo - if user cancel ask it they want to kill on all machines.. then write stop all renders file
# todo - how to make the missing dpx run for stuff that gets killed? - keep the log files in the data dict and process all?

WATCHFOLDER = '/Users/tom/Desktop/watch/'
NUMBER_ENGINES = 4
AERENDER = '/Applications/Adobe After Effects CS6/aerender'
STRFTIMEFORLOGS = '_%m%d%y_%H_%M.txt'
WAIT_TIME = 60 # seconds
__version__ = '0.7b'

import subprocess
import datetime
import multiprocessing
import os
import sys
import traceback
from time import sleep
from signal import SIGTERM
from glob import glob

from pprint import pprint


def is_it_ok_to_render_project(full_path_to_ae_project_file): #tested OK
    '''
    Given a path to an after effects project file, returns a boolean that
    tells if the file should be rendered.

    If there is a file called "_project_stopped.txt" return False
    If there is a file called "_render_complete.txt" return False
    If the RCF file does not contain "item" on any line then MAY be OK
        if the RCF has item but does not have "working" then return False
    '''
    containing_path = os.path.split(full_path_to_ae_project_file)[0]
    if os.path.exists(os.path.join(containing_path, '_project_stopped.txt')) or os.path.exists(
            os.path.join(containing_path, '_render_complete.txt')):
        return False

    for rcf_file in glob(os.path.join(containing_path, '*RCF.txt')):
        # there will only be one item in this list...
        # print rcf_file
        with open(rcf_file, 'r') as f:
            rcf_contents = f.read()
            if 'item' not in rcf_contents:
                return True
            elif 'Working' not in rcf_contents and 'In Progress' not in rcf_contents:
                return False
                # if we get here without returning then the RCF indicates that we can proceed
    return True

def error_report(error_line):
        if 'mov' in error_line and 'Unable' in error_line:
            return "ERROR: Movie Render Error" # OK to ignore
        elif 'Can not create a file' in error_line:
            return "ERROR: File Access Error" #OK to ignore
        else:
            return "ERROR: Undefined Error (Check Logs)"

def error_report(error_line):
    if 'mov' in error_line and 'Unable' in error_line:
        return "ERROR: Movie Render Error - This is an expected error and should be ignored" # OK to ignore
    elif 'Can not create a file' in error_line:
        return "ERROR: File Access Error. Job should be rerun in a few minutes" #OK to ignore
    else:
        return "ERROR: Undefined Error (Please Check Log For More Info)\n"+error_line

def success_report(success_line):
    return "SUCCESS: Successful render"

def deal_with_possible_zeros(error_log_output_to_info):
    datum = error_log_output_to_info.split('Output To: ')
    path_to_check = os.path.dirname(datum[-1])

    if not os.path.exists(path_to_check):
        return

    curdir = os.getcwd()
    os.chdir(path_to_check)
    # check the dpx frames
    # todo add a check for jpg frames
    files_to_check = glob('*.dpx')
    bad_dpx = set([afile for afile in files_to_check if os.stat(afile).st_size < 8000000])
    if bad_dpx:
        print 'Found bad frames - waiting to see if they are not being rendered by another machine'
        sleep(90) # change to 3 minutes for production
        bad_dpx2 = set([afile for afile in files_to_check if os.stat(afile).st_size < 8000000])

        really_bad_dpx = bad_dpx & bad_dpx2
        report_to_user = bad_dpx & bad_dpx2
        for file in really_bad_dpx:
            try:
                os.remove(file)
                report_to_user.remove(file)
            except:
                print 'COULD NOT DELETE {}'.format(file)
        os.chdir(curdir)
        return report_to_user
    os.chdir(curdir)
    return

def get_grinder_error(phile, zero_only = False):
    with open(phile, 'r') as f:
        lines = f.read().splitlines()
        for i in range(3):
            try:
                this_line = lines[-i - 1]
                if 'Error' in this_line:
                    if not zero_only: return error_report(this_line)
                    break
                elif 'Elapsed' in this_line:
                    if not zero_only: return success_report(this_line)
                    break

            except IndexError:
                #return "ERROR: Early Death Of Engine (Check zero frames)"
                if not zero_only: return success_report(this_line)
                break # short log files mean a kind of error that is expected and can be ignored
                # probably an early death, start looking for a path
        while lines:
            this_line = lines.pop() # we want to find the LAST place that the output was going...
            if 'Output To' in this_line:
                death_check = deal_with_possible_zeros(this_line)
                if death_check:
                    return "ERROR: Early Death Of Engine (Check zero frames) - {}".format(death_check)
                else:
                    if not zero_only: return "WARNING: Early Death of Engine - no zero frames found"
                #break

        # return "Dropped to bottom - ERROR: Early Death Of Engine (Check zero frames)"

class RenderInstance(multiprocessing.Process):
    def __init__(self, task_queue, result_queue):
        multiprocessing.Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        proc_name = self.name
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                # Poison pill means shutdown
                print '                                         %s: Exiting' % proc_name
                self.task_queue.task_done()
                self.result_queue.put(('end', 0, 'end'))
                break
            print '                                          %s: %s' % (proc_name, next_task)
            answer = next_task(proc_name)
            self.task_queue.task_done()
            self.result_queue.put(answer)
        return

# the thing that does the work and accepts arguments...
class Task(object):
    def __init__(self, project_path, log_file_base_path_and_name):
        self.project_path = project_path
        containing_path = os.path.split(project_path)[0]
        self.log_file_path = os.path.join(containing_path, log_file_base_path_and_name)
        # this is where the worker doers their work!

    def __call__(self, proc_name):
        # it is expected that a lot of the processes will fail - they always fail for movie renders - so catch and release
        if not is_it_ok_to_render_project(self.project_path):
            # another process has finished this while the job was sitting in the queue
            return (self.project_path, 0)

        log_file_path = self.log_file_path + str(proc_name) + datetime.datetime.now().strftime(STRFTIMEFORLOGS)
        # redirecting stdout and stderr to dev/null to silence the additional noise the aerender generates
        with open(os.devnull, 'wb') as null_out:
            return_code = subprocess.call([AERENDER, '-project', self.project_path, '-log',
                                       log_file_path], stdout=null_out, stderr=null_out)
        error_message = 'Success...'
        if return_code:
            error_message = get_grinder_error(log_file_path)
        return (self.project_path, return_code, log_file_path, error_message)

    def __str__(self):
        return '%s ' % (self.project_path)

class WaitTask(object):
    'A task that waits 10 mintues and then returns "wait over"'
    def __init__(self, ):
        pass

    # this is where the worker doers their work!
    def __call__(self, proc_name):
        sleep(WAIT_TIME) # 300 = 5 minutes to let other processes wrap up cleanly
        return ('wait over', 0, None, 'wait over')

    def __str__(self):
        return 'waiting 1 minute'

class AE_Render_Manager(object):
    '''
    This is primarily an object so that all the information that needs to be passed between routines can be encapsulated'

    log_file_name_prefix: the text to use for the log file name. Will have the "machine name" added and an identifier for
        the specific worker too... eg: 'Render_Log_' ==> "Render_Log_Borg_Instance1.txt (for example)


    '''
    def __init__(self, watchfolder_path, number_of_engines, path_to_aerender, log_file_name_prefix,
                 machine_name, log_folder_name ):
        self.number_of_workers = number_of_engines
        self.stop_work = False
        self.worker_count = number_of_engines
        self.watchfolder_path = watchfolder_path
        self.waiting_jobs_list = [] # note that each job gets pushed onto the list number_of_engines times
        self.machine_name = machine_name
        self.log_folder_name = log_folder_name
        self.log_file_base_name = log_file_name_prefix + self.machine_name
        self.jobs_in_process_dict = {}
        self._create_queues()
        self._create_workers()
        self._get_jobs_from_filesystem()
        self._prime_queue()
        self.process_names_to_kill = frozenset([ 'aerender', 'aerendercore'] )

    def _check_or_create_log_folder(self, aep_file_path):
        container_directory = os.path.split(aep_file_path)[0]
        log_folder_path = os.path.join(container_directory, self.log_folder_name)
        if not os.path.exists(log_folder_path):
            os.mkdir(log_folder_path)

    def _get_jobs_from_filesystem(self): # tested
        '''
        go to the filesystem and look at an AE watch folder. look at RCF files and associated "stop" files
        then set self.active_job_list appropriately (sorted to give highest priority first)
        '''
        subfolders = os.listdir(self.watchfolder_path)
        ok_aep_file_paths = []
        for folder in subfolders:
            current_path = os.path.join(self.watchfolder_path, folder)
            aep_file_path = glob(os.path.join(current_path, '*.aep'))
            if not aep_file_path:
                # no aep file! so just continue
                continue
            aep_file_path = aep_file_path[0]
            if is_it_ok_to_render_project(aep_file_path):
                # the aep file passes the good-to-go test so add it to the list
                ok_aep_file_paths.append(aep_file_path)
        ok_aep_file_paths.sort(reverse=True) # reverse sort so that pop takes the right one off list
        for aep_file_path in ok_aep_file_paths:
            self._check_or_create_log_folder(aep_file_path)
        self.waiting_jobs_list = []
        #clean out the existing list and then add the found jobs, n times each, in sort order
        for apath in ok_aep_file_paths:
            for i in range(self.number_of_workers):
                self.waiting_jobs_list.append(apath)
                # for l in [ [x]*self.number_of_workers for x in ok_aep_file_paths]:
                #     self.waiting_jobs_list.extend(l)

    def _create_queues(self): # tested in prior code versions
        '''
        set up the communication queues (job queue and message queue)
        '''
        # Establish communication queues
        self.task_queue = multiprocessing.JoinableQueue()
        self.result_queue = multiprocessing.Queue()

    def _create_workers(self): # tested in prior code versions
        '''
        set up the worker tasks and start them running
        '''
        # Start instances
        print 'Creating {} instances'.format(self.number_of_workers)
        self.worker_instances_list = [RenderInstance(self.task_queue, self.result_queue) for i in
                                      xrange(self.number_of_workers)]
        for worker in self.worker_instances_list:
            worker.start()

    def _prime_queue(self): # tested
        '''
        Fill the queue with tasks (an initialization process). Put one more task that there are workers
        '''
        for i in range(self.number_of_workers + 1):
            sleep(2) # pause briefly to let ae NOT over-run itself with simultaneous requests to same file
            self._push_job_to_queue()

    def _job_queued_data_tracking(self, aep_file_path):
        '''
        encapulate data tracking efforts that get managed when a job is added to the queue
        '''
        if aep_file_path not in self.jobs_in_process_dict:
            # initialize the data collector before updating
            self.jobs_in_process_dict[aep_file_path] = {
                "time put on queue": set(),
                "time job errored": set(),
                "success flag": False,
                "resubmitted flag": False,
                "count": 0
            }
        self.jobs_in_process_dict[aep_file_path]["time put on queue"].add(datetime.datetime.now())
        self.jobs_in_process_dict[aep_file_path]["count"] += 1

    def _is_it_ok_to_add_this_job(self, path_to_project_file):
        '''
        return True is OK to push the job onto the queue, False otherwise

        AND ALSO update the data tracking based on how the decision was made!
        ====================================================================
        '''
        if not is_it_ok_to_render_project(path_to_project_file):
            # if we shouldn't render the project because of text-file flags return False
            return False

        if path_to_project_file in self.jobs_in_process_dict:
            current_proj_dict = self.jobs_in_process_dict[path_to_project_file]
            # one set of logic if we are already trakcing the project
            time_now = datetime.datetime.now()
            if current_proj_dict['count'] >= self.number_of_workers:
                return False
            if current_proj_dict['success flag']:
                return False
            if current_proj_dict['resubmitted flag']:
                return False
            if current_proj_dict['time job errored']:
                # we have had at least one error
                # check the time and resubmit if appropriate, updating info as you go...
                if time_now - min(current_proj_dict['time put on queue']) < datetime.timedelta(seconds=60):
                    return True
                elif time_now - max(current_proj_dict['time job errored']) > datetime.timedelta(seconds=60 * 5):
                    current_proj_dict['resubmitted flag'] = True
                    return True
                else:
                    return False
            return True # nothing to stop us from adding to the queue so go ahead

        else: # different logic if this is a new project
            return is_it_ok_to_render_project(path_to_project_file)

    def _push_job_to_queue(self):
        '''
        encapuslate logic to decide what job gets pushed onto the queue next and then push it onto the queue
        '''

        while self.waiting_jobs_list:
            this_job = self.waiting_jobs_list.pop()
            # queue management logic here!
            if self._is_it_ok_to_add_this_job(this_job):
                log_path_and_base_name = os.path.join(self.log_folder_name, self.log_file_base_name)
                self.task_queue.put(Task(this_job, log_path_and_base_name))
                self._job_queued_data_tracking(this_job)
                break

        else:
            #push wait tasks onto the queue
            # print 'pusihg wait task'
            # print self.stop_work
            if self.stop_work:
                pass
            else:
                self.task_queue.put(WaitTask())
                sleep(int(WAIT_TIME/self.number_of_workers)) # pause between wait pushes to keep things spread out in time


    def _on_success_do(self, path_to_rendered_project):
        containing_path = os.path.split(path_to_rendered_project)[0]
        success_file_path = os.path.join(containing_path, '_completed.txt')
        subprocess.call(['touch', "{}".format(success_file_path)])
        success_file_path = os.path.join(containing_path, '_project_stopped.txt')
        subprocess.call(['touch', "{}".format(success_file_path)])
        self.jobs_in_process_dict[path_to_rendered_project]["success flag"] = True
        if self.jobs_in_process_dict[path_to_rendered_project]['count'] <= 0:
            # clean up the job by removing it from the dict - project will not rerender
            del self.jobs_in_process_dict[path_to_rendered_project]


    def _on_failure_do(self, path_to_rendered_project): #todo - getting errors for success flag not in dict... fix
        # pprint (self.jobs_in_process_dict)
        if (self.jobs_in_process_dict[path_to_rendered_project]['count'] <= 0
            and
                self.jobs_in_process_dict[path_to_rendered_project]['success flag']):
            # clean up the job by removing it from the dict - project will not rerender
            del self.jobs_in_process_dict[path_to_rendered_project]
        else:
            self.jobs_in_process_dict[path_to_rendered_project]['time job errored'].add(datetime.datetime.now())

    def _handle_output_from_queue(self, path_to_rendered_project,
                                  aerender_result_code, path_to_log_file, error_message):
        '''
        when the queue has output in it, do what needs to be done...
        Mostly logic that helps track what has been done to facilitate the decision about what to add to queue next
        '''
        if path_to_rendered_project == 'end':
            # this is the marker that tells us a worker has killed itself by request
            return # without adding anything to the queue or handling data, the task is not "real"
        if path_to_rendered_project != 'wait over':
            #this was NOT a wait task...

            self.jobs_in_process_dict[path_to_rendered_project]["count"] -= 1

            if aerender_result_code: #  a 1 - this means that aerender errored
                self._on_failure_do(path_to_rendered_project)

            else: # a 0 - aerender exited cleanly and processed all items in the RQ correctly
                self._on_success_do(path_to_rendered_project)

        # after I process the output and update tracking data used to manage queue. Then...
        self._get_jobs_from_filesystem() #always update from filesystem before pushing to queue
        self._push_job_to_queue()

    def _quit_elegantly(self): # todo - poll log files for output locations and delete zeor byte (or small) files
        '''
        a clean up routine to allow the user to cancel the operation without leaving all the renders still in progress
        the method of accomplishing this is still TBD but a standard render does not use aerender to do it's work
        so we should be able to use ps | grep aerender and then send kill notices to the PID's. Can't just terminate the
        workers
        '''
        print 'Attempting to exit cleanly'
        for worker in self.worker_instances_list:
            print '...Killing the workers'
            worker.terminate()
            # how to find a process by name and kill it???
        pidlines = subprocess.check_output(['ps', '-axc'])
        for line in pidlines.splitlines():
            split_line = line.split()
            if split_line[3] in self.process_names_to_kill:
                #kill pid line split_line[0]
                print '...Killing a running instance of AE'
                os.kill(int(split_line[0]), SIGTERM)
        # todo note - do I need to check for the SIGTERM success and issue a SIGKILL?
        print '\n'*3
        _note = '''
            currently, killing the AE renders this way causes them to leave half written files...
            with SIGTERM :killing aerender but not aerendercore does not stop processing at all
             asked question here - http://forums.adobe.com/thread/1173443 but no answers yet.
        '''

    def results_iterator(self): # tested
        '''
        an iterator that will yield either a result, or None each time it is looped over
        Implementing as an iterator so that it can be put into a PyQt Application in a way that will not
        halt the UI. Mainly so that there can be a Pause or Cancel button that will allow the user to kill
        all the current rendering processes.
        '''
        while True:
            if self.result_queue.empty():
                yield None
            else:
                results_from_worker = self.result_queue.get() #note, this will lock if the queue is actually empty...
                self._handle_output_from_queue(*results_from_worker)
                yield results_from_worker

    def _notes(self):
        self.notes = '''
                # notes about what is discovered during testing

                If there is a movie output in the queue, it will be rerendered even if the file already exists but, once the
                RQ gets to that point, all processes trying to render the same queue will be halted except one.

                This means that if the movie comes before ANY frames, you will end up with only one instance working on all future
                frame renders (unless we catch errors and then restart but then you will always have one that gets trapped on the movie
                and the rest will fail!)

                When starting a bunch of instances at the same time, they seem to collide when trying to access the same frame and
                die a horrible death... spreading out the start time of the spin-up makes the problem almost disappear

                The render writes render logs to the same location as the aep file so that I don't even have to keep track of logging!
                I can even specify a full path with file name for the output so that we can know what machine and what instance...

                There is no indication in the logs when an effect is not licensed correctly (Re:vision, I'm worrying about you!)

                _project_stopped.txt indicates to the watch folder that the shot is "done". I will use _completed.txt to indicate a
                successful completion of the project

                Even if I kill the spawned processes, aerender will continue to run because it is NOT spawned by me and it is not
                bound to me either - they will run in BG until they complete or get killed by PID...

                A full instance of AE, when rendering, does not leave an aerender process running. Need to check
                and see if the render engine uses it (so that I can kill the render engines if needed)

                When done, if exiting cleanly parse the log files to find out where the files are being rendered to
                and delete zero length (or very small) files
                        '''


if __name__ == '__main__':
    watchfolder_path = '/Users/tom/Desktop/watch'
    number_of_engines = 3

    # get name of machine procedurally
    from socket import gethostname
    machine_name = gethostname().split('.')[0]
    path_to_aerender = '/Applications/Adobe After Effects CS6/aerender'
    log_file_name_prefix = 'Grinder_Log_' # did not work ==> os.path.join('render_test.aep Logs', 'Grinder_Log_')
    log_folder_name = 'Grinder_Logs'
    # set up temporary command line arguments
    import optparse
    option_parser = optparse.OptionParser(version='Grinder version {}'.format(__version__))
    option_parser.add_option('-w', '--watchfolder', help='Specify The Path To The Watch Folder',
                             dest='watchfolder_path', action='store')
    option_parser.add_option('-n', dest='number_of_engines', action='store', type='int',
                             help='how many aerender instances should be started by this program')
    (opts, args) = option_parser.parse_args()
    mandatories = ('watchfolder_path' , 'number_of_engines')
    for m in mandatories:
        if not opts.__dict__[m]:
            print "mandatory option is missing\n"
            option_parser.print_help()
            exit(-1)

    number_of_engines = int(opts.number_of_engines)
    watchfolder_path = opts.watchfolder_path
    # comment out block to here to turn off option parsing and revert to hard coded values

    print
    print '*' * 80
    print 'Grinder will run for 3 hours and then stop itself during this beta phase... To exit early type Control-C'
    print '  in the Terminal window. If you stop Grinder while aerender is rendering frames you will have'
    print '  zero byte frames left behind. If it was processing a movie, the movie will be truncated or corrupt.'
    print 'NOTE - any render with mov files as output is expected to fail for all but one instance!'
    print '*' * 80
    print

    manager = AE_Render_Manager(watchfolder_path, number_of_engines, path_to_aerender, log_file_name_prefix,
                                machine_name, log_folder_name)
    start_time = datetime.datetime.now()
    try:
        timeout = False
        for output in manager.results_iterator():
            sys.stdout.flush()
            # print 'inside result infinte loop'
            if not timeout and datetime.datetime.now() - start_time > datetime.timedelta(
                    seconds = 60 * 180): # 1 minute (for testing of kill procedure)
                # print 'inside time out loop'
                manager.stop_work = True
                # raise Exception
                # Add a poison pill for each instance
                for i in range(manager.number_of_workers):
                    manager.task_queue.put(None)
                timeout = True
                # break
            sleep(20)
            # print 'done sleeping'
            if output:
                # print 'got some output', output
                message, return_code, log_path, error_message  = output
                if message == 'wait over':
                    pass
                elif message == 'end':
                    # print 'got the end message'
                    # there has been a worker that ended by request... how do I end processing?
                    if manager.worker_count > 1:
                        manager.worker_count -= 1
                    else:
                        break # to cleanly exit the infinite loop
                else:
                    print
                    print '*' * 80
                    print '{}: {} finished processing'.format(datetime.datetime.now(),os.path.split(message)[-1] )
                    if return_code :
                        # print 'The render engine reported an error during processing - see the logs for more info'
                        print error_message
                        print '     Log File:', log_path
                    else:
                        print 'The render completed all queued comps successfully'
                    print '*' * 80
            # else:
            #     print '.',
            #     sys.stdout.flush()

    except KeyboardInterrupt:
        print 'You killed this process: if a render was in progress there may be some zero byte frames left behind!'

    except Exception,e:
        print str(e)
        #traceback.print_exc()
    finally:
        sleep(1)
        all_logs = set()
        for aep_file_path in manager.jobs_in_process_dict.keys():
            container_path = os.path.dirname(aep_file_path)
            all_logs.update(glob('{}/{}/*'.format(container_path, log_folder_name)))
            # will then process the log files looking for zero frames and deleting them...
        manager._quit_elegantly()
        print 'Looking For Zero Byte Frames and Deleting Them - this may take a while!'
        for log_file in all_logs:
            this_error =get_grinder_error(log_file, zero_only=True)
            if this_error:
                print this_error
        print 'done'
