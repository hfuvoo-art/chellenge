import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
// В облачной песочнице используем установленный Chromium. На своём компьютере строку можно удалить.
if (process.env.REMOTION_CHROME) {
  Config.setBrowserExecutable(process.env.REMOTION_CHROME);
}
