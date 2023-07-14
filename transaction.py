#!/usr/bin/env python
# SETMODE 777

# ----------------------------------------------------------------------------------------#
# ------------------------------------------------------------------------------ HEADER --#

"""
:author:
    Nick Maclean

:synopsis:
    Transaction system for performing operations within a scope with rollback support.

:description:
    Performing supported actions with a transaction allow them to be undone or aborted.
    Example: copying a series of files from one location to another. If there is an
    error during the process, the transaction would stop copying files and undo copies
    that have been completed. Restoring the state prior to when the transaction began.
"""

# ----------------------------------------------------------------------------------------#
# ----------------------------------------------------------------------------- IMPORTS --#

# Built-In
from abc import ABC, abstractmethod
from enum import Enum
import os.path
import shutil
import tempfile
import traceback

# ----------------------------------------------------------------------------------------#
# -------------------------------------------------------------------------- EXCEPTIONS --#

class TransactionAbortError(Exception):
    """
    Error that can be thrown to force an abort. Will work even if transaction is not safe.
    """
    pass


class TransactionError(Exception):
    """
    Errors during a transaction. These will never cause the transaction to auto-abort.
    """
    pass


class CommandError(Exception):
    """
    Errors during a command. Usually related to calling a command's methods in the
    wrong order.
    """
    pass

# ----------------------------------------------------------------------------------------#
# ----------------------------------------------------------------------------- CLASSES --#

class TransactionState(Enum):
    NONE = "None"
    INIT = "Initialized"
    RUNNING = "Running"
    DONE = "Done"
    ABORTED = "Aborted"


class Transaction(object):
    def __init__(self, name=None, verbose=False, safe=True):
        """
        :param name: A name for the transaction. Used for debugging.
        :type: str
        :param verbose: enable optional data to be displayed to the console
        :type: bool
        :param safe: auto-abort if any errors occur during the transaction. Intended for debugging.
        :type: bool
        """
        self.name = name
        self.verbose = verbose
        self.safe = safe

        self.state = TransactionState.INIT
        self.commands = []
        self.temp_dir = None

    @classmethod
    def execute(cls, commands: list['CommandBase'], name=None, verbose=False, safe=True):
        """
        Convenience method to automatically create a transaction to execute the
        provided commands.

        :return: success
        :type: bool
        """
        with Transaction(name, verbose, safe) as transaction:
            transaction.perform_commands(commands)

        return transaction.state == TransactionState.DONE

    def start(self):
        try:
            self.__enter__()
        except TransactionError:
            return False
        finally:
            return True

    def perform_command(self, command: 'CommandBase'):
        """
        Performs command. If this transaction is not safe, exceptions will not be caught.
        It becomes the user's responsibility to catch an exceptions. Otherwise, all
        exceptions (except TransactionErrors) will be caught and cause the transaction to
        automatically abort.

        :param command: command to be performed
        :type: CommandBase
        """
        if self.state != TransactionState.RUNNING:
            raise TransactionError("The transaction is not running. Commands cannot be "
                                   "performed now.")

        self.commands.append(command)
        command.perform(self.temp_dir)

    def perform_commands(self, commands: list['CommandBase']):
        """
        Wraps self.perform_command to perform commands in the order provided.
        :param commands:
        """
        for command in commands:
            self.perform_command(command)

    def abort(self):
        """
        Aborts the transaction, which rolls back any commands that were performed.
        Calling this method multiple times will raise a TransactionError.
        """
        if self.state == TransactionState.ABORTED:
            raise TransactionError("Transaction has already been aborted. It cannot be "
                                   "aborted again.")

        self.state = TransactionState.ABORTED

        for cmd in reversed(self.commands):
            cmd.rollback()

    def end(self):
        try:
            self.__exit__(None, None, None)
        except TransactionError:
            return False
        finally:
            return True

    def _commit(self):
        for cmd in self.commands:
            cmd.commit()

    def __enter__(self):
        if self.state == TransactionState.NONE:
            raise TransactionError("Cannot enter transaction. Transaction state is "
                                   "invalid.")
        if self.state == TransactionState.DONE or self.state == TransactionState.ABORTED:
            raise TransactionError("Cannot enter transaction. Transaction has already "
                                   f"been {self.state.value}.")
        if self.state == TransactionState.RUNNING:
            print("WARNING: entering transaction that is already running.")

        # create temp directory for commands
        self.temp_dir = tempfile.mkdtemp(prefix="_")
        if self.verbose:
            print(f"INFO: {self.name} Transaction's temp dir is {self.temp_dir}")
        if not os.path.isdir(self.temp_dir):
            raise TransactionError("Failed to create temp directory.")

        self.state = TransactionState.RUNNING
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # case: no error
        if exc_val is None:
            # if self.state is aborted, self.abort has already been called. We don't need
            # to call it again.
            if self.state == TransactionState.ABORTED:
                self._cleanup()
                return True

            if self.state == TransactionState.NONE:
                raise TransactionError("Cannot exit transaction. Transaction state is "
                                       "invalid.")
            if self.state == TransactionState.INIT:
                raise TransactionError("Cannot exit transaction. Transaction has not "
                                       f"been started.")
            if self.state == TransactionState.DONE:
                print("WARNING: exiting transaction that has already been completed.")
                return True
            else:
                self._commit()

            self.state = TransactionState.DONE
            self._cleanup()
            return True

        # case: handle error
        # always let TransactionError's be raised
        if isinstance(exc_val, TransactionError):
            return False

        error_is_abort = isinstance(exc_val, TransactionAbortError)

        # Transaction is not safe, let the error be raised
        if not self.safe and not error_is_abort:
            return False

        if self.verbose and not error_is_abort:
            print(f"ERROR: {self.name} was forced to abort.")
            traceback.print_exception(exc_type, exc_val, exc_tb)
        self.abort()

        # clean up temp directory
        self._cleanup()
        return True

    def _cleanup(self):
        shutil.rmtree(self.temp_dir)


class CommandState(Enum):
    INIT = "Initialized"
    PERFORMED = "Performed"
    ROLLEDBACK = "Rolledback"
    COMMITTED = "Committed"


class CommandBase(ABC):
    """
    Base class for commands. Intended to be used within Transactions to enable do/undo.

    Child classes can use base abstract methods to automatically manage command state.
    They track what methods have been performed and catch errors from calling methods
    multiple times or if they have been called in the wrong order. state can be ignored
    if the command has no state.

    See also: Command allows creating instances that define the abstract methods using
    delegates, but inheriting from this class allows you to do define commands too.
    """
    def __init__(self):
        self._state = CommandState.INIT
        self._error_pre_preform = False

    @abstractmethod
    def perform(self, temp_dir):
        """
        Collect state information to support possible rollback and perform the desired
        action.
        :param temp_dir: provided temp directory for any data stored between perform
        and rollback/commit
        """
        if self._state != CommandState.INIT:
            self._error_pre_preform = True
            raise CommandError("Commands may only be performed once and it must be "
                               "before rollback and commit.")
        self._state = CommandState.PERFORMED

    @abstractmethod
    def rollback(self):
        """
        Undo any changes made during perform.
        :return: If true, children calling this method should not rollback.
        """
        # Transaction will try to rollback this command, even though its state is still
        # INIT. Just let child class calls know to ignore this.
        if self._error_pre_preform:
            return True

        if self._state != CommandState.PERFORMED:
            raise CommandError("Commands may only be rolledback once and it must be "
                               "after performing it and it must not have been committed.")

        return False

    @abstractmethod
    def commit(self):
        """
        Cleanup any changes made during self.perform to support rollback that are no
        longer needed. Example: for CommandFileWrite, if a temp copy was saved in case
        rollback, go ahead and delete it. The transaction was successful so we can
        commit to the command.

        Technically, if the only cleanup is to files in the temp dir, this can be
        skipped. Transaction will delete the temp dir (and its contents) on abort or
        exit, so this method can ignore those changes. On principle, this method should
        still clean up those changes.
        """
        if self._state != CommandState.PERFORMED:
            raise CommandError("Commands may only be committed once and it must be "
                               "after perming it and it must not have been rolledback.")
        self._state = CommandState.COMMITTED

    def execute(self, name=None, verbose=False):
        """
        Convenience method to perform this single action in a Transaction.
        This will create a transaction, perform the transaction, then exit.

        :param name: name for wrapping transaction. Defaults to class name if None.
        :param verbose:

        :return: success
        :type: bool
        """
        if not name:
            name = self.__class__.__name__

        with Transaction(name=name, verbose=verbose) as transaction:
            transaction.perform_command(self)

        return transaction.state == TransactionState.DONE


class Command(CommandBase):
    """
    Initialized CommandBase with delegates so no inheritance is necessary.
    """
    def __init__(self, perform, rollback, commit):
        """
        :param perform: function to override self.perform(str temp_dir)
        :param rollback: function to override self.rollback()
        :param commit: function to override self.commit()
        """
        super().__init__()
        self.perform_callback = perform
        self.rollback_callback = rollback
        self.commit_callback = commit

    def perform(self, temp_dir):
        super().perform(temp_dir) # allow base class to manage state
        self.perform_callback()

    def rollback(self):
        if super().rollback(): return True # allow base class to manage state
        self.rollback_callback()

    def commit(self):
        super().commit() # allow base class to manage state
        self.commit_callback()


class CommandAbort(CommandBase):
    """
    Command to trigger the containing transaction to abort.
    """
    # noinspection PyMissingConstructor
    def __init__(self):
        pass

    def perform(self, temp_dir):
        raise TransactionAbortError

    def rollback(self):
        pass

    def commit(self):
        pass


class _CommandFileBase(CommandBase, ABC):
    """
    Base class for performing file operations as Commands.
    The base functionality is as follows:
      perform(temp_dir): save a copy, return true if there was a file to copy
      rollback(): restore from copy, delete copy, return true if there was a copy
      commit(): delete copy
    """
    def __init__(self, target_path: str):
        super().__init__()
        self.target_path = target_path
        self._temp_copy = None

    def perform(self, temp_dir):
        super().perform(temp_dir) # allow base class to manage state

        # if file is already present, save a copy in case a rollback is needed
        # return true if there is a copy
        will_overwrite = os.path.isfile(self.target_path)
        if will_overwrite:
            (copy_file, copy_dest) = tempfile.mkstemp(dir=temp_dir)
            os.close(copy_file)
            self._temp_copy = shutil.copy(self.target_path, copy_dest)

        return will_overwrite

    def rollback(self):
        if super().rollback(): return True # allow base class to manage state

        # restore file from copy and delete copy
        # return true if there was a copy
        if not self._temp_copy or not os.path.isfile(self._temp_copy):
            return False

        shutil.move(self._temp_copy, self.target_path)
        return True

    def commit(self):
        super().commit() # allow base class to manage state

        # remove temp copy, we no longer need it
        if not self._temp_copy or not os.path.isfile(self._temp_copy):
            return

        os.remove(self._temp_copy)


class CommandFileWrite(_CommandFileBase):
    """
    Wrapper for file.write(str)
    """
    def __init__(self, target_path: str, contents: str):
        super().__init__(target_path)
        self.contents = contents

    def perform(self, temp_dir):
        super().perform(temp_dir)

        # write to file
        with open(self.target_path, 'w') as file:
            file.write(self.contents)

    def rollback(self):
        if super().rollback():
            return

        # there was no copy, lets delete the file we made
        if not os.path.isfile(self.target_path):
            return
        os.remove(self.target_path)
        return


class CommandFileDelete(_CommandFileBase):
    """
    Wrapper for os.remove(str)
    """
    def perform(self, temp_dir):
        if not super().perform(temp_dir):
            return False

        # delete file
        os.remove(self.target_path)


class CommandFileCopy(_CommandFileBase):
    """
    Wrapper for shutil.copy(str, str)
    """
    def __init__(self, src_path: str, dst_path: str):
        if src_path == dst_path:
            raise shutil.SameFileError(f"'{src_path}' and '{dst_path}' are the same file.")

        # swap to protect destination file during rollback
        super().__init__(dst_path)
        self.src_path = src_path
        self.dst_path = dst_path

    def perform(self, temp_dir):
        super().perform(temp_dir)

        if not self.src_path or not os.path.isfile(self.src_path):
            return False

        shutil.copy(self.src_path, self.dst_path)

    def rollback(self):
        # destination was restored
        if super().rollback():
            return True

        # there was no file before the copy
        # destroy the new file created during perform
        if not self.dst_path or not os.path.isfile(self.dst_path):
            return False

        os.remove(self.dst_path)


class CommandFileMove(_CommandFileBase):
    """
    Wrapper for shutil.move(str, str)
    """
    def __init__(self, target_path, dst_path):
        super().__init__(dst_path)
        self.src_path = target_path
        self.dst_path = dst_path

    def perform(self, temp_dir):
        super().perform(temp_dir)

        if not self.src_path or not os.path.isfile(self.src_path):
            return False

        shutil.move(self.src_path, self.dst_path)

    def rollback(self):
        # restore source file
        if self.dst_path and os.path.isfile(self.dst_path):
            shutil.move(self.dst_path, self.src_path)

        # restore destination file
        super().rollback()

# ----------------------------------------------------------------------------------------#
# -------------------------------------------------------------------------------- MAIN --#

def main():
    # with Transaction("File Write", verbose=True, safe=False) as transaction:
    #     from datetime import datetime
    #     transaction.perform_commands([
    #         CommandFileDelete('A:/temp.txt'),
    #         CommandFileWrite('A:/temp.txt', f"hello :: {datetime.now()} :)"),
    #         CommandAbort(),
    #     ])

    # scoped transaction
    # with Transaction() as transaction:
    #     transaction.perform_command(CommandFileDelete('A:/temp.txt'))

    # single command
    # result = CommandFileDelete('A:/temp.txt').execute()
    # print(result)

    # multi command
    # result = Transaction.execute([
    #     CommandFileDelete('A:/temp.txt'),
    # ])
    # print(result)

    with Transaction(verbose=True, safe=False) as transaction:
        transaction.perform_command(CommandFileMove('A:/temp.txt', 'A:/temp2.txt'))
        transaction.perform_command(CommandFileCopy('A:/temp1.txt', 'A:/temp2.txt'))
        transaction.abort()

# ----------------------------------------------------------------------------------------#
# ----------------------------------------------------------------------- DEFAULT START --#

if __name__ == '__main__':
    main()
