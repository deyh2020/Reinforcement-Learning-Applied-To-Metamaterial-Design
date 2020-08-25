import matlab.engine
import torch
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from torchvision import transforms
from PIL import Image
import io

## 4 Cylinder TSCS calculator
class TSCSEnv():
	"""docstring for TSCSEnv"""
	def __init__(self):
		## Matlab interface
		self.eng = matlab.engine.start_matlab()
		self.eng.addpath('TSCS')
		self.nCyl = 4
		self.stepSize = 0.5

		## State variables
		self.img = None
		self.config = None
		self.TSCS = None
		self.RMS = None

		## Image transform
		self.img_dim = 50
		self.transform = transforms.Compose([
			transforms.Resize((self.img_dim, self.img_dim)),
			transforms.ToTensor(),
			transforms.Normalize(1, 1)])

	def validConfig(self, config):
		"""
		Checks if config is within bounds and does not overlap cylinders
		"""
		withinBounds = False
		overlap = False
		if (-5 < config).all() and (config < 5).all():
			withinBounds = True

			coords = config.view(self.nCyl, 2)
			for i in range(self.nCyl):
				for j in range(self.nCyl):
					if i != j:
						x1, y1 = coords[i]
						x2, y2 = coords[j]
						d = torch.sqrt((x2-x1)**2 + (y2-y1)**2)
						if d <= 1:
							overlap = True
		return withinBounds and not overlap

	def getIMG(self, config):
		fig, ax = plt.subplots(figsize=(6, 6))
		ax.axis('equal')
		ax.set_xlim(xmin=-6, xmax=6)
		ax.set_ylim(ymin=-6, ymax=6)
		ax.grid()

		config = config.view(self.nCyl, 2)
		for cyl in range(self.nCyl):
			ax.add_artist(Circle((config[cyl, 0], config[cyl, 1]), radius=0.5))
		buf = io.BytesIO()
		plt.savefig(buf, format='png')
		buf.seek(0)
		im = Image.open(buf)
		X = self.transform(im)
		buf.close()
		return X

	def render(self):
		img = self.getIMG(self.config)
		plt.imshow(img.type(torch.uint8).view(self.img_dim, self.img_dim, 4))
		plt.show()

	def getConfig(self):
		valid = False
		while not valid:
			config = torch.FloatTensor(1, 8).uniform_(-5, 5)
			if self.validConfig(config):
				break
		return config

	def getTSCS(self, config):
		tscs = self.eng.getTSCS4CYL(*self.config.squeeze(0).tolist())
		return torch.tensor(tscs).T

	def getRMS(self, config):
		rms = self.eng.getRMS4CYL(*self.config.squeeze(0).tolist())
		return torch.tensor(rms)

	def getReward(self, TSCS, nextTSCS):
		s0 = TSCS.mean().item()
		s1 = nextTSCS.mean().item()
		avg = (s0 + s1)/2
		reward = 10/avg*(TSCS - nextTSCS).mean().item()
		return reward

	def reset(self):
		self.config = self.getConfig()
		self.TSCS = self.getTSCS(self.config)
		state = (self.config, self.TSCS)
		return state

	def getNextConfig(self, config, action):
		## Applys action to config
		coords = config.view(self.nCyl, 2)
		cyl = int(action/4)
		direction = action % 4
		if direction == 0:
			coords[cyl, 0] -= self.stepSize
		if direction == 1:
			coords[cyl, 1] += self.stepSize
		if direction == 2:
			coords[cyl, 0] += self.stepSize
		if direction == 3:
			coords[cyl, 1] -= self.stepSize
		nextConfig = coords.view(1, 2 * self.nCyl)
		return nextConfig

	def step(self, action):
		nextConfig = self.getNextConfig(self.config, action)
		## If the config after applying the action is not valid
		# we revert back to previous state and give negative reward
		# otherwise, reward is calculated by the change in scattering
		done = False
		if not self.validConfig(nextConfig):
			reward = -10.0
			done = True
		else:
			nextTSCS = self.getTSCS(nextConfig)
			reward = self.getReward(self.TSCS, nextTSCS)
			self.config = nextConfig
			self.TSCS = nextTSCS

		state = (self.config, self.TSCS)
		return state, reward, done

if __name__ == '__main__':
	env = TSCSEnv()
	state = env.reset()
	config, tscs = state

	done = False
	while not done:
		env.render()
		action = int(input("Action: "))
		state,reward,done=env.step(action)
		print(reward)